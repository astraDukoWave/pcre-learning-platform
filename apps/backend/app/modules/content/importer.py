"""Importación idempotente de borradores (REQ-07, ADR-03).

- Valida todo antes de escribir: si el lint tiene errores, no escribe nada.
- Una sola transacción para todas las rutas.
- Upsert de ruta, unidades, fuentes e ítems; revisión `draft` nueva solo si cambió el
  hash; guarda `source_path` y `source_commit`.
- Nunca aprueba ni publica.
"""

from __future__ import annotations

import os
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db.uow import UnitOfWorkFactory
from app.modules.content import repository
from app.modules.content.activity_rows import activity_columns
from app.modules.content.lint import audio_status, lint_dir
from app.modules.content.loader import ContentBundle, Issue
from app.modules.content.models import (
    Activity,
    ContentItem,
    ContentRevision,
    LearningPath,
    RevisionSource,
    Source,
    Unit,
)
from app.modules.content.schema import (
    AssessmentFormFile,
    LessonFile,
    RecordedSpeakingActivity,
    ScenarioFile,
    content_hash,
    item_payload,
)


class ImportAborted(Exception):
    def __init__(self, issues: list[Issue]) -> None:
        self.issues = issues
        super().__init__(f"el lint tiene {len(issues)} errores; no se importó nada")


@dataclass
class ImportResult:
    path_code: str
    created: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    refreshed: list[str] = field(default_factory=list)
    warnings: int = 0

    def render(self) -> str:
        return (
            f"{self.path_code}: {len(self.created)} revisiones nuevas, "
            f"{len(self.refreshed)} borradores actualizados, {len(self.unchanged)} sin cambios, "
            f"{self.warnings} advertencias" + "".join(f"\n  + {c}" for c in self.created)
        )


def detect_source_commit(content_root: Path) -> str | None:
    for var in ("SOURCE_COMMIT", "HEROKU_SLUG_COMMIT", "SOURCE_VERSION", "GITHUB_SHA"):
        value = os.environ.get(var, "").strip()
        if value:
            return value[:64]
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            cwd=content_root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip()[:64] or None


def run_import(
    uow: UnitOfWorkFactory, content_root: Path, *, now: datetime, source_commit: str | None
) -> list[ImportResult]:
    linted = lint_dir(content_root)
    errors = [i for _, issues in linted.values() for i in issues if i.severity == "error"]
    if errors:
        raise ImportAborted(errors)
    results = []
    with uow() as s:
        for bundle, issues in linted.values():
            results.append(_import_bundle(s, bundle, issues, now, source_commit))
    return results


def _audio_url(bundle: ContentBundle, audio_id: str | None) -> str | None:
    if not audio_id or audio_status(bundle, audio_id) != "ready":
        return None
    entry = next(a for a in bundle.audio.audio if a.id == audio_id)
    return f"/media/{entry.file}"


def _activity_rows(bundle: ContentBundle, item: Any) -> list[dict[str, Any]]:
    rubrics = {r.id: r for r in bundle.rubrics.rubrics} if bundle.rubrics else {}
    rows = []
    for position, act in enumerate(item.activities, start=1):
        cols = activity_columns(act, rubrics)
        cols["position"] = position
        if cols["stimulus"] and cols["stimulus"].get("audio"):
            cols["stimulus"]["audio_url"] = _audio_url(bundle, cols["stimulus"]["audio"])
        if isinstance(act, RecordedSpeakingActivity) and cols["options"] is not None:
            cols["options"]["audio_url"] = _audio_url(bundle, act.audio)
        rows.append(cols)
    return rows


def _import_bundle(
    s: Session,
    bundle: ContentBundle,
    issues: list[Issue],
    now: datetime,
    source_commit: str | None,
) -> ImportResult:
    assert bundle.path is not None and bundle.sources is not None
    spec = bundle.path
    result = ImportResult(
        path_code=spec.code, warnings=sum(i.severity == "warning" for i in issues)
    )

    path = repository.path_by_code(s, spec.code)
    fields = {
        "exam_code": spec.exam_code,
        "exam_format_version": spec.exam_format_version,
        "level_from": spec.level_from,
        "level_to": spec.level_to,
        "title": spec.title,
        "label": spec.label,
        "catalog_version": spec.catalog_version,
    }
    if path is None:
        path = LearningPath(id=uuid.uuid4(), code=spec.code, status="active", **fields)
        s.add(path)
        s.flush()
    else:
        for key, value in fields.items():
            setattr(path, key, value)

    # Unidades: posiciones temporales negativas para permitir reordenar sin chocar.
    existing_units = {u.slug: u for u in repository.units_of(s, path.id)}
    s.execute(update(Unit).where(Unit.path_id == path.id).values(position=-Unit.position))
    unit_ids: dict[str, uuid.UUID] = {}
    for entry in spec.units:
        unit = existing_units.get(entry.slug)
        if unit is None:
            unit = Unit(
                id=uuid.uuid4(),
                path_id=path.id,
                slug=entry.slug,
                position=entry.position,
                title=entry.title,
                summary=entry.summary,
            )
            s.add(unit)
        else:
            unit.position, unit.title, unit.summary = entry.position, entry.title, entry.summary
        unit_ids[entry.slug] = unit.id
    s.flush()

    source_ids: dict[str, uuid.UUID] = {}
    for src in bundle.sources.sources:
        src_row = repository.source_by_key(s, src.id)
        if src_row is None:
            src_row = Source(
                id=uuid.uuid4(),
                key=src.id,
                url=src.url,
                title=src.title,
                publisher=src.publisher,
                accessed_on=src.accessed_on,
                status=src.status,
            )
            s.add(src_row)
        else:
            src_row.url, src_row.title, src_row.publisher = src.url, src.title, src.publisher
            src_row.accessed_on, src_row.status = src.accessed_on, src.status
        source_ids[src.id] = src_row.id
    s.flush()

    for loaded in bundle.items:
        item = loaded.model
        if item is None:
            continue
        unit_slug = getattr(item, "unit", None)
        db_item = repository.item_by_slug(s, path.id, item.slug)
        item_fields = {
            "kind": item.kind,
            "unit_id": unit_ids.get(unit_slug) if unit_slug else None,
            "position": item.position,
            "skill": item.skill if isinstance(item, LessonFile) else None,
            "form_kind": item.form_kind if isinstance(item, AssessmentFormFile) else None,
            "title": item.title,
        }
        if db_item is None:
            db_item = ContentItem(id=uuid.uuid4(), path_id=path.id, slug=item.slug, **item_fields)
            s.add(db_item)
            s.flush()
        else:
            for key, value in item_fields.items():
                setattr(db_item, key, value)

        payload = item_payload(item)
        digest = content_hash(payload)
        file_issues = [i for i in issues if i.file == loaded.file and i.severity == "warning"]
        warnings = [
            {"code": i.code, "message": i.message, "activity": i.activity} for i in file_issues
        ]
        audio_pending = any(i.code == "pending_audio" for i in file_issues)
        rows = _activity_rows(bundle, item)
        label = f"{item.slug}"

        existing = repository.revision_by_hash(s, db_item.id, digest, lock=True)
        if existing is not None:
            # El cuerpo de una revisión aprobada es inmutable, pero su estado de audio y sus
            # advertencias se reevalúan: un audio que vuelve a quedar sin revisar bloquea
            # publicar (hallazgo 3 de CS-04). Lo publicado o retirado no se toca.
            if existing.status in ("draft", "approved"):
                existing.lint_warnings = warnings
                existing.audio_pending = audio_pending
                _refresh_audio_urls(s, existing.id, rows)
                if existing.status == "draft":
                    existing.file_status = item.status
                result.refreshed.append(f"{label} v{existing.version} ({existing.status})")
            else:
                result.unchanged.append(f"{label} v{existing.version} ({existing.status})")
            continue

        version = repository.max_version(s, db_item.id) + 1
        rev = ContentRevision(
            id=uuid.uuid4(),
            item_id=db_item.id,
            version=version,
            content_hash=digest,
            body=payload,
            source_path=f"content/{loaded.file}",
            source_commit=source_commit,
            status="draft",
            file_status=item.status,
            lint_errors=0,
            lint_warnings=warnings,
            audio_pending=audio_pending,
            created_at=now,
        )
        s.add(rev)
        s.flush()
        for row in rows:
            s.add(Activity(id=uuid.uuid4(), revision_id=rev.id, **row))
        for claim in item.sources:
            s.add(
                RevisionSource(
                    id=uuid.uuid4(),
                    revision_id=rev.id,
                    source_id=source_ids[claim.source],
                    claim=claim.claim,
                    scope=claim.scope,
                    location=claim.location,
                )
            )
        if isinstance(item, LessonFile):
            for rule in item.pcre.rules:
                if rule.source and rule.source in source_ids:
                    s.add(
                        RevisionSource(
                            id=uuid.uuid4(),
                            revision_id=rev.id,
                            source_id=source_ids[rule.source],
                            claim=rule.text,
                            scope=rule.applies_when_not_es or "regla de la explicación",
                            location=None,
                        )
                    )
        if isinstance(item, ScenarioFile | AssessmentFormFile | LessonFile):
            result.created.append(f"{label} v{version}")
    s.flush()
    return result


def _refresh_audio_urls(s: Session, revision_id: uuid.UUID, rows: list[dict[str, Any]]) -> None:
    """En un borrador, el audio revisado después de importar actualiza su URL."""
    by_key = {r["activity_key"]: r for r in rows}
    for act in repository.activities_of(s, revision_id):
        row = by_key.get(act.activity_key)
        if row is None:
            continue
        if row["stimulus"] != act.stimulus:
            act.stimulus = row["stimulus"]
        if row["options"] != act.options:
            act.options = row["options"]
