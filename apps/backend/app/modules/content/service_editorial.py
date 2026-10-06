"""Flujo editorial (REQ-08): revisiones, hallazgos, aprobación por hash, publicación atómica
y retiro. Solo una persona administradora decide; ningún camino de código deja que un
modelo apruebe o publique (las decisiones exigen el id de quien decide)."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.db.uow import UnitOfWorkFactory
from app.modules.content import domain, repository
from app.modules.content.importer import ImportResult, detect_source_commit, run_import
from app.modules.content.models import (
    ContentItem,
    ContentReport,
    ContentRevision,
    EditorialDecision,
    ReviewFinding,
    Unit,
)
from app.modules.content.service_delivery import Mode, item_dto
from app.modules.insights import service as insights

logger = logging.getLogger("app.content")

REVIEW_CHECKLIST = (
    "El objetivo es observable y coincide con el mapa.",
    "La explicación es correcta y cada regla tiene fuente y alcance.",
    "Los ejemplos son originales y no ambiguos.",
    "Las claves están verificadas y las variantes válidas, listadas.",
    "Los distractores son plausibles y no hay dos respuestas defendibles.",
    "El apoyo en español aparece solo donde se permite.",
    "El audio coincide con el guion y se entiende.",
    "Hay alternativas de accesibilidad (transcripción, texto alternativo).",
    "No hay marcadores pendientes y el lint está limpio.",
)


@dataclass(frozen=True)
class PublishedRef:
    revision_id: uuid.UUID
    item_slug: str
    version: int


def _facts(s: Session, rev: ContentRevision) -> domain.RevisionFacts:
    return domain.RevisionFacts(
        status=rev.status,
        content_hash=rev.content_hash,
        approved_hash=rev.approved_hash,
        open_material_findings=repository.open_material_findings(s, rev.id),
        lint_errors=rev.lint_errors,
        audio_pending=rev.audio_pending,
    )


def _blocked(blockers: list[str]) -> Conflict:
    return Conflict(domain.describe(blockers), code=blockers[0])


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _lock_for_decision(s: Session, revision_id: uuid.UUID) -> tuple[ContentRevision, ContentItem]:
    """Orden fijo de bloqueo: primero el ítem, después la revisión. Publicar, publicar
    unidad y retirar lo comparten, así no hay bloqueos mutuos (hallazgo 2 de CS-04)."""
    plain = s.get(ContentRevision, revision_id)
    if plain is None:
        raise NotFound()
    item = repository.item_for_update(s, plain.item_id)
    rev = repository.revision(s, revision_id, lock=True)
    if item is None or rev is None:
        raise NotFound()
    return rev, item


class EditorialService:
    def __init__(self, uow: UnitOfWorkFactory, clock: Clock) -> None:
        self.uow = uow
        self.clock = clock

    # -- importación ---------------------------------------------------------------------

    def import_dir(self, content_root: Path) -> list[ImportResult]:
        return run_import(
            self.uow,
            content_root,
            now=self.clock.now(),
            source_commit=detect_source_commit(content_root),
        )

    # -- lectura -------------------------------------------------------------------------

    def list_revisions(
        self,
        *,
        kind: str | None = None,
        status: str | None = None,
        unit_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        with self.uow() as s:
            rows = repository.list_revisions(s, kind=kind, status=status, unit_id=unit_id)
            return [
                {
                    "id": str(rev.id),
                    "item_id": str(item.id),
                    "item_slug": item.slug,
                    "item_title": item.title,
                    "kind": item.kind,
                    "skill": item.skill,
                    "form_kind": item.form_kind,
                    "unit": {"id": str(unit.id), "slug": unit.slug, "title": unit.title}
                    if unit
                    else None,
                    "version": rev.version,
                    "status": rev.status,
                    "file_status": rev.file_status,
                    "content_hash": rev.content_hash,
                    "is_published": item.published_revision_id == rev.id,
                    "warnings": len(rev.lint_warnings or []),
                    "audio_pending": rev.audio_pending,
                    "open_material_findings": repository.open_material_findings(s, rev.id),
                    "created_at": rev.created_at.isoformat(),
                }
                for rev, item, unit in rows
            ]

    def list_units(self) -> list[dict[str, Any]]:
        with self.uow() as s:
            units = s.scalars(select(Unit).order_by(Unit.position))
            return [
                {"id": str(u.id), "slug": u.slug, "title": u.title, "position": u.position}
                for u in units
            ]

    def revision_detail(self, revision_id: uuid.UUID) -> dict[str, Any]:
        with self.uow() as s:
            rev = repository.revision(s, revision_id)
            if rev is None:
                raise NotFound()
            item = s.get(ContentItem, rev.item_id)
            assert item is not None
            activities = [
                {
                    "id": str(a.id),
                    "key": a.activity_key,
                    "position": a.position,
                    "format": a.format,
                    "task_family": a.task_family,
                    "pool": a.pool,
                    "objectives": list(a.objective_codes),
                    "prompt": a.prompt,
                    "stimulus": a.stimulus,
                    "data": a.options,
                    "hints": a.hints,
                    "support_es": a.support_es,
                    "transcript": a.transcript,
                    "example": a.example,
                    "solution": a.solution,
                    "explanation": a.explanation,
                    "rubric": a.rubric,
                }
                for a in repository.activities_of(s, rev.id)
            ]
            all_pools = ("practice", "review", "assessment")
            preview_mode: Mode = "assessment" if item.kind == "assessment_form" else "practice"
            return {
                "id": str(rev.id),
                "item": {
                    "id": str(item.id),
                    "slug": item.slug,
                    "title": item.title,
                    "kind": item.kind,
                    "skill": item.skill,
                    "form_kind": item.form_kind,
                    "published_revision_id": str(item.published_revision_id)
                    if item.published_revision_id
                    else None,
                },
                "version": rev.version,
                "status": rev.status,
                "file_status": rev.file_status,
                "content_hash": rev.content_hash,
                "approved_hash": rev.approved_hash,
                "approved_at": _iso(rev.approved_at),
                "published_at": _iso(rev.published_at),
                "withdrawn_at": _iso(rev.withdrawn_at),
                "withdraw_reason": rev.withdraw_reason,
                "source_path": rev.source_path,
                "source_commit": rev.source_commit,
                "lint_errors": rev.lint_errors,
                "lint_warnings": rev.lint_warnings,
                "audio_pending": rev.audio_pending,
                "body": rev.body,
                "activities": activities,
                "sources": [
                    {
                        "key": src.key,
                        "url": src.url,
                        "title": src.title,
                        "publisher": src.publisher,
                        "status": src.status,
                        "accessed_on": src.accessed_on.isoformat() if src.accessed_on else None,
                        "claim": rs.claim,
                        "scope": rs.scope,
                        "location": rs.location,
                    }
                    for rs, src in repository.sources_of(s, rev.id)
                ],
                "findings": [_finding(f) for f in repository.findings_of(s, rev.id)],
                "decisions": [
                    {
                        "action": d.action,
                        "decided_by": str(d.decided_by),
                        "content_hash": d.content_hash,
                        "note": d.note,
                        "created_at": d.created_at.isoformat(),
                    }
                    for d in repository.decisions_of(s, rev.id)
                ],
                "checklist": list(REVIEW_CHECKLIST),
                "preview_practice": item_dto(s, item, rev, mode=preview_mode, pools=all_pools),
                "preview_assessment": item_dto(s, item, rev, mode="assessment", pools=all_pools),
                "blockers": {
                    "approve": domain.approval_blockers(_facts(s, rev), rev.content_hash),
                    "publish": domain.publish_blockers(_facts(s, rev)),
                },
            }

    # -- hallazgos -----------------------------------------------------------------------

    def add_finding(
        self,
        revision_id: uuid.UUID,
        *,
        by: uuid.UUID,
        category: str,
        severity: str,
        description: str,
    ) -> dict[str, Any]:
        if severity not in domain.FINDING_SEVERITIES:
            raise ValidationFailed("Severidad inválida.", code="severity_invalid")
        with self.uow() as s:
            rev = repository.revision(s, revision_id)
            if rev is None:
                raise NotFound()
            finding = ReviewFinding(
                id=uuid.uuid4(),
                revision_id=rev.id,
                author=f"user:{by}",
                created_by=by,
                category=category,
                severity=severity,
                description=description,
                status="open",
                created_at=self.clock.now(),
            )
            s.add(finding)
            s.flush()
            return _finding(finding)

    def update_finding(
        self, finding_id: uuid.UUID, *, status: str, resolution_note: str | None
    ) -> dict[str, Any]:
        if status not in domain.FINDING_STATUSES:
            raise ValidationFailed("Estado inválido.", code="status_invalid")
        with self.uow() as s:
            finding = s.get(ReviewFinding, finding_id)
            if finding is None:
                raise NotFound()
            finding.status = status
            finding.resolution_note = resolution_note
            finding.resolved_at = None if status == "open" else self.clock.now()
            s.flush()
            return _finding(finding)

    # -- decisiones ----------------------------------------------------------------------

    def _decide(
        self, s: Session, rev: ContentRevision, action: str, by: uuid.UUID, note: str | None
    ) -> None:
        s.add(
            EditorialDecision(
                id=uuid.uuid4(),
                revision_id=rev.id,
                action=action,
                decided_by=by,
                content_hash=rev.content_hash,
                note=note,
                created_at=self.clock.now(),
            )
        )

    def approve(
        self, revision_id: uuid.UUID, *, by: uuid.UUID, content_hash: str, note: str | None = None
    ) -> dict[str, Any]:
        with self.uow() as s:
            rev, _item = _lock_for_decision(s, revision_id)
            blockers = domain.approval_blockers(_facts(s, rev), content_hash)
            if blockers:
                raise _blocked(blockers)
            rev.status = "approved"
            rev.approved_by = by
            rev.approved_at = self.clock.now()
            rev.approved_hash = rev.content_hash
            self._decide(s, rev, "approve", by, note)
        logger.info("revision_approved", extra={"revision_id": str(revision_id)})
        return self.revision_detail(revision_id)

    def _publish_locked(
        self, s: Session, rev: ContentRevision, item: ContentItem, by: uuid.UUID, note: str | None
    ) -> None:
        blockers = domain.publish_blockers(_facts(s, rev))
        if blockers:
            raise _blocked(blockers)
        now = self.clock.now()
        s.execute(
            update(ContentRevision)
            .where(ContentRevision.item_id == item.id, ContentRevision.status == "published")
            .values(status="superseded")
        )
        rev.status = "published"
        rev.published_at = now
        item.published_revision_id = rev.id
        self._decide(s, rev, "publish", by, note)

    def publish(
        self, revision_id: uuid.UUID, *, by: uuid.UUID, note: str | None = None
    ) -> dict[str, Any]:
        with self.uow() as s:
            rev, item = _lock_for_decision(s, revision_id)
            self._publish_locked(s, rev, item, by, note)
        logger.info("revision_published", extra={"revision_id": str(revision_id)})
        return self.revision_detail(revision_id)

    def publish_unit(self, unit_id: uuid.UUID, *, by: uuid.UUID) -> list[PublishedRef]:
        """Publica en lote lo aprobado de una unidad: todo o nada."""
        published: list[PublishedRef] = []
        with self.uow() as s:
            if s.get(Unit, unit_id) is None:
                raise NotFound()
            # Ítems primero (en orden de id), después sus revisiones.
            list(
                s.scalars(
                    select(ContentItem)
                    .where(ContentItem.unit_id == unit_id)
                    .order_by(ContentItem.id)
                    .with_for_update()
                )
            )
            rows = s.execute(
                select(ContentRevision, ContentItem)
                .join(ContentItem, ContentItem.id == ContentRevision.item_id)
                .where(ContentItem.unit_id == unit_id, ContentRevision.status == "approved")
                .order_by(ContentItem.position, ContentRevision.version.desc())
                .with_for_update(of=ContentRevision)
            )
            seen: set[uuid.UUID] = set()
            for rev, item in [(r[0], r[1]) for r in rows]:
                if item.id in seen:
                    continue
                seen.add(item.id)
                self._publish_locked(s, rev, item, by, "publicación de la unidad")
                published.append(PublishedRef(rev.id, item.slug, rev.version))
            if not published:
                raise Conflict(
                    "No hay revisiones aprobadas en esta unidad.", code="nothing_to_publish"
                )
        return published

    def withdraw(self, revision_id: uuid.UUID, *, by: uuid.UUID, reason: str) -> dict[str, Any]:
        with self.uow() as s:
            rev, item = _lock_for_decision(s, revision_id)
            blockers = domain.withdraw_blockers(rev.status, reason)
            if blockers:
                raise _blocked(blockers)
            rev.status = "withdrawn"
            rev.withdrawn_at = self.clock.now()
            rev.withdraw_reason = reason.strip()
            if item.published_revision_id == rev.id:
                item.published_revision_id = None
            self._decide(s, rev, "withdraw", by, reason.strip())
        logger.info("revision_withdrawn", extra={"revision_id": str(revision_id)})
        return self.revision_detail(revision_id)

    # -- reportes del alumno -------------------------------------------------------------

    def report(
        self,
        *,
        user_id: uuid.UUID,
        revision_id: uuid.UUID,
        activity_id: uuid.UUID | None,
        attempt_id: uuid.UUID | None,
        category: str,
        message: str,
        page: str | None,
    ) -> uuid.UUID:
        if category not in domain.REPORT_CATEGORIES:
            raise ValidationFailed("Elige una categoría.", code="category_invalid")
        with self.uow() as s:
            rev = repository.revision(s, revision_id)
            if rev is None or rev.published_at is None:
                raise NotFound()
            if activity_id is not None and activity_id not in {
                a.id for a in repository.activities_of(s, rev.id)
            }:
                raise NotFound()
            if attempt_id is not None:
                # Solo un intento propio (y de esa actividad): un recurso ajeno o inexistente
                # responde 404 sin revelar si existe (NFR-01, EDGE-06).
                owner = repository.attempt_owner(s, attempt_id)
                if (
                    owner is None
                    or owner[0] != user_id
                    or (activity_id is not None and owner[1] != activity_id)
                ):
                    raise NotFound()
            report = ContentReport(
                id=uuid.uuid4(),
                user_id=user_id,
                revision_id=rev.id,
                activity_id=activity_id,
                attempt_id=attempt_id,
                category=category,
                message=message.strip(),
                page=page,
                status="open",
                created_at=self.clock.now(),
            )
            repository.add_report(s, report)
            insights.emit(s, user_id, "content_reported", report.created_at, category=category)
            return report.id

    def reports(self, status: str | None) -> list[dict[str, Any]]:
        with self.uow() as s:
            return [_report(r, title) for r, title in repository.reports(s, status)]

    def triage_report(
        self, report_id: uuid.UUID, *, status: str, note: str | None
    ) -> dict[str, Any]:
        if status not in domain.REPORT_STATUSES:
            raise ValidationFailed("Estado de reporte desconocido.", code="status_invalid")
        with self.uow() as s:
            found = repository.report(s, report_id)
            if found is None:
                raise NotFound()
            report, title = found
            report.status = status
            report.triage_note = (note or "").strip() or None
            s.flush()
            return _report(report, title)


def _report(r: ContentReport, title: str | None) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "revision_id": str(r.revision_id),
        "item_title": title,
        "activity_id": str(r.activity_id) if r.activity_id else None,
        "attempt_id": str(r.attempt_id) if r.attempt_id else None,
        "category": r.category,
        "message": r.message,
        "page": r.page,
        "status": r.status,
        "triage_note": r.triage_note,
        "created_at": r.created_at.isoformat(),
    }


def _finding(f: ReviewFinding) -> dict[str, Any]:
    return {
        "id": str(f.id),
        "author": f.author,
        "category": f.category,
        "severity": f.severity,
        "description": f.description,
        "status": f.status,
        "resolution_note": f.resolution_note,
        "created_at": f.created_at.isoformat(),
        "resolved_at": _iso(f.resolved_at),
    }
