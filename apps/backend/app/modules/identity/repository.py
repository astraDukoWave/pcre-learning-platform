"""Consultas de identidad. Todo recurso de alumno se filtra por `user_id`."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Table, delete, func, select, update
from sqlalchemy.orm import Session

from app.db.base import Base
from app.modules.identity.data_registry import REGISTRY
from app.modules.identity.models import AuthSession, Invitation, PasswordResetToken, User


def user_by_id(session: Session, user_id: uuid.UUID) -> User | None:
    return session.get(User, user_id)


def user_by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == email))


def session_by_token_hash(session: Session, token_hash: str) -> AuthSession | None:
    return session.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash))


def revoke_user_sessions(session: Session, user_id: uuid.UUID, now: datetime, reason: str) -> int:
    result = session.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now, revoke_reason=reason)
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


def invitation_by_token_hash(session: Session, token_hash: str) -> Invitation | None:
    return session.scalar(
        select(Invitation).where(Invitation.token_hash == token_hash).with_for_update()
    )


def expire_pending_invitations(session: Session, email: str, now: datetime) -> None:
    session.execute(
        update(Invitation)
        .where(
            Invitation.email == email,
            Invitation.consumed_at.is_(None),
            Invitation.expires_at > now,
        )
        .values(expires_at=now)
    )


def reset_by_token_hash(session: Session, token_hash: str) -> PasswordResetToken | None:
    return session.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == token_hash)
        .with_for_update()
    )


def expire_pending_resets(session: Session, user_id: uuid.UUID, now: datetime) -> None:
    session.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.consumed_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .values(expires_at=now)
    )


def lock_email(session: Session, email: str) -> None:
    """Serializa la creación de invitaciones por email (lock consultivo de la transacción)."""
    session.execute(select(func.pg_advisory_xact_lock(func.hashtext(f"invite:{email}"))))


def delete_invitations_for_email(session: Session, email: str) -> None:
    session.execute(delete(Invitation).where(Invitation.email == email))


def list_users(session: Session) -> list[User]:
    return list(session.scalars(select(User).order_by(User.created_at, User.email)))


def delete_user(session: Session, user_id: uuid.UUID) -> None:
    session.execute(delete(User).where(User.id == user_id))


def _jsonable(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return None
    return value


def export_rows(session: Session, user_id: uuid.UUID) -> dict[str, list[dict[str, Any]]]:
    """Filas del usuario en cada tabla registrada con `export=True` (lectura por metadata:
    no importa modelos de otros módulos)."""
    out: dict[str, list[dict[str, Any]]] = {}
    for name, entry in sorted(REGISTRY.items()):
        if not entry.export:
            continue
        table: Table = Base.metadata.tables[name]
        column = table.c[entry.user_columns[0]]
        order = [c for c in (table.c.get("created_at"), table.c.get("id")) if c is not None]
        rows = session.execute(select(table).where(column == user_id).order_by(*order))
        out[name] = [
            {k: _jsonable(v) for k, v in row._mapping.items() if k not in entry.exclude_columns}
            for row in rows
        ]
    return out
