"""Consultas de contenido."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.content.models import (
    Activity,
    ContentItem,
    ContentReport,
    ContentRevision,
    EditorialDecision,
    LearningPath,
    ReviewFinding,
    RevisionSource,
    Source,
    Unit,
)


def path_by_code(s: Session, code: str) -> LearningPath | None:
    return s.scalar(select(LearningPath).where(LearningPath.code == code))


def units_of(s: Session, path_id: uuid.UUID) -> list[Unit]:
    return list(s.scalars(select(Unit).where(Unit.path_id == path_id).order_by(Unit.position)))


def source_by_key(s: Session, key: str) -> Source | None:
    return s.scalar(select(Source).where(Source.key == key))


def item_by_slug(s: Session, path_id: uuid.UUID, slug: str) -> ContentItem | None:
    return s.scalar(
        select(ContentItem).where(ContentItem.path_id == path_id, ContentItem.slug == slug)
    )


def item_for_update(s: Session, item_id: uuid.UUID) -> ContentItem | None:
    return s.scalar(select(ContentItem).where(ContentItem.id == item_id).with_for_update())


def revision_by_hash(
    s: Session, item_id: uuid.UUID, content_hash: str, *, lock: bool = False
) -> ContentRevision | None:
    stmt = select(ContentRevision).where(
        ContentRevision.item_id == item_id, ContentRevision.content_hash == content_hash
    )
    if lock:
        stmt = stmt.with_for_update()
    return s.scalar(stmt)


def max_version(s: Session, item_id: uuid.UUID) -> int:
    value = s.scalar(
        select(func.max(ContentRevision.version)).where(ContentRevision.item_id == item_id)
    )
    return int(value or 0)


def revision(s: Session, revision_id: uuid.UUID, *, lock: bool = False) -> ContentRevision | None:
    stmt = select(ContentRevision).where(ContentRevision.id == revision_id)
    if lock:
        stmt = stmt.with_for_update()
    return s.scalar(stmt)


def activities_of(s: Session, revision_id: uuid.UUID) -> list[Activity]:
    return list(
        s.scalars(
            select(Activity).where(Activity.revision_id == revision_id).order_by(Activity.position)
        )
    )


def open_material_findings(s: Session, revision_id: uuid.UUID) -> int:
    return int(
        s.scalar(
            select(func.count())
            .select_from(ReviewFinding)
            .where(
                ReviewFinding.revision_id == revision_id,
                ReviewFinding.severity == "material",
                ReviewFinding.status == "open",
            )
        )
        or 0
    )


def findings_of(s: Session, revision_id: uuid.UUID) -> list[ReviewFinding]:
    return list(
        s.scalars(
            select(ReviewFinding)
            .where(ReviewFinding.revision_id == revision_id)
            .order_by(ReviewFinding.created_at)
        )
    )


def decisions_of(s: Session, revision_id: uuid.UUID) -> list[EditorialDecision]:
    return list(
        s.scalars(
            select(EditorialDecision)
            .where(EditorialDecision.revision_id == revision_id)
            .order_by(EditorialDecision.created_at)
        )
    )


def sources_of(s: Session, revision_id: uuid.UUID) -> list[tuple[RevisionSource, Source]]:
    rows = s.execute(
        select(RevisionSource, Source)
        .join(Source, Source.id == RevisionSource.source_id)
        .where(RevisionSource.revision_id == revision_id)
        .order_by(Source.key, RevisionSource.claim)
    )
    return [(row[0], row[1]) for row in rows]


def list_revisions(
    s: Session, *, kind: str | None, status: str | None, unit_id: uuid.UUID | None
) -> Sequence[tuple[ContentRevision, ContentItem, Unit | None]]:
    stmt = (
        select(ContentRevision, ContentItem, Unit)
        .join(ContentItem, ContentItem.id == ContentRevision.item_id)
        .outerjoin(Unit, Unit.id == ContentItem.unit_id)
        .order_by(Unit.position.nulls_first(), ContentItem.position, ContentRevision.version.desc())
    )
    if kind:
        stmt = stmt.where(ContentItem.kind == kind)
    if status:
        stmt = stmt.where(ContentRevision.status == status)
    if unit_id:
        stmt = stmt.where(ContentItem.unit_id == unit_id)
    return [(row[0], row[1], row[2]) for row in s.execute(stmt)]


def published_items(s: Session, path_id: uuid.UUID) -> list[ContentItem]:
    return list(
        s.scalars(
            select(ContentItem)
            .where(ContentItem.path_id == path_id, ContentItem.published_revision_id.is_not(None))
            .order_by(ContentItem.position)
        )
    )


def active_paths(s: Session) -> list[LearningPath]:
    """Rutas activas con al menos un ítem publicado."""
    has_published = (
        select(ContentItem.id)
        .where(
            ContentItem.path_id == LearningPath.id,
            ContentItem.published_revision_id.is_not(None),
        )
        .exists()
    )
    return list(
        s.scalars(
            select(LearningPath)
            .where(LearningPath.status == "active", has_published)
            .order_by(LearningPath.code)
        )
    )


def add_report(s: Session, report: ContentReport) -> None:
    s.add(report)
