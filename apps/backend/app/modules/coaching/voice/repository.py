"""Acceso a datos de las sesiones de voz. Lee el escenario publicado desde `content`."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.modules.coaching.voice.models import VoiceSession
from app.modules.content.models import ContentItem, ContentRevision

# Llave del lock consultivo que serializa el cupo global de sesiones (REQ-05).
QUOTA_LOCK_KEY = 4_020_517
LIVE = ("reserved", "active")


def lock_quota(s: Session) -> None:
    s.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": QUOTA_LOCK_KEY})


def live_count(s: Session) -> int:
    return int(s.scalar(select(func.count()).where(VoiceSession.status.in_(LIVE))) or 0)


def user_live(s: Session, user_id: uuid.UUID) -> VoiceSession | None:
    return s.scalars(
        select(VoiceSession).where(VoiceSession.user_id == user_id, VoiceSession.status.in_(LIVE))
    ).first()


def add(s: Session, session: VoiceSession) -> None:
    s.add(session)
    s.flush()


def get(s: Session, session_id: uuid.UUID, *, lock: bool = False) -> VoiceSession | None:
    stmt = select(VoiceSession).where(VoiceSession.id == session_id)
    if lock:
        stmt = stmt.with_for_update()
    return s.scalars(stmt).one_or_none()


def for_user(s: Session, user_id: uuid.UUID, session_id: uuid.UUID) -> VoiceSession | None:
    return s.scalars(
        select(VoiceSession).where(VoiceSession.id == session_id, VoiceSession.user_id == user_id)
    ).one_or_none()


def by_run(s: Session, run_id: uuid.UUID) -> VoiceSession | None:
    return s.scalars(select(VoiceSession).where(VoiceSession.ai_run_id == run_id)).one_or_none()


def published_scenario(
    s: Session, item_id: uuid.UUID
) -> tuple[ContentItem, ContentRevision] | None:
    item = s.get(ContentItem, item_id)
    if item is None or item.kind != "scenario" or item.published_revision_id is None:
        return None
    rev = s.get(ContentRevision, item.published_revision_id)
    return (item, rev) if rev is not None else None


def revision_body(s: Session, revision_id: uuid.UUID) -> dict[str, object]:
    rev = s.get(ContentRevision, revision_id)
    return dict(rev.body) if rev is not None else {}


def stale(s: Session, *, reserved_before: datetime, active_before: datetime) -> list[VoiceSession]:
    """Huérfanas: `reserved` creadas antes de `reserved_before` y `active` cuyo deadline pasó
    antes de `active_before`. Bloqueadas sin esperar a otra transacción."""
    return list(
        s.scalars(
            select(VoiceSession)
            .where(
                ((VoiceSession.status == "reserved") & (VoiceSession.created_at < reserved_before))
                | ((VoiceSession.status == "active") & (VoiceSession.deadline_at < active_before))
            )
            .with_for_update(skip_locked=True)
        )
    )
