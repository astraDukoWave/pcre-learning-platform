"""Casos de uso de identidad: invitaciones, sesiones, perfil, reset, exportación y borrado."""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import (
    AppError,
    Conflict,
    NotFound,
    RateLimited,
    Unauthorized,
    ValidationFailed,
)
from app.core.logging import user_ref
from app.core.security import (
    Passwords,
    constant_time_equals,
    derive_csrf_token,
    hash_token,
    new_token,
)
from app.db.uow import UnitOfWorkFactory
from app.modules.identity import domain, repository
from app.modules.identity.models import AuthSession, Invitation, PasswordResetToken, User, UserRole

logger = logging.getLogger("app.identity")

_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")

PASSWORD_MESSAGES = {
    "password_too_short": "La contraseña debe tener al menos 10 caracteres.",
    "password_too_long": "La contraseña puede tener como máximo 128 caracteres.",
    "password_equals_email": "La contraseña no puede ser igual a tu correo.",
}


class LinkInvalid(AppError):
    status_code = 410
    code = "link_invalid"
    default_message = "Este enlace ya no sirve. Pide uno nuevo a quien te invitó."


class InvalidCredentials(AppError):
    status_code = 401
    code = "invalid_credentials"
    default_message = "Correo o contraseña incorrectos."


@dataclass(frozen=True)
class AuthContext:
    user_id: uuid.UUID
    role: str
    session_id: uuid.UUID
    csrf_hash: str
    is_internal: bool
    timezone: str


@dataclass(frozen=True)
class UserView:
    id: uuid.UUID
    email: str
    role: str
    display_name: str | None
    timezone: str
    goal_purpose: str | None
    target_exam: str | None
    target_exam_other: str | None
    target_score: str | None
    target_date: date | None
    self_reported_level: str | None
    onboarded: bool
    consent_version: str | None
    is_internal: bool
    created_at: datetime
    last_login_at: datetime | None


@dataclass(frozen=True)
class IssuedSession:
    token: str
    csrf_token: str
    expires_at: datetime
    user: UserView


@dataclass(frozen=True)
class IssuedLink:
    token: str
    expires_at: datetime
    email: str


@dataclass(frozen=True)
class AdminUserView:
    user: UserView
    active_sessions: int


def _view(user: User) -> UserView:
    return UserView(
        id=user.id,
        email=user.email,
        role=user.role.value,
        display_name=user.display_name,
        timezone=user.timezone,
        goal_purpose=user.goal_purpose,
        target_exam=user.target_exam,
        target_exam_other=user.target_exam_other,
        target_score=user.target_score,
        target_date=user.target_date,
        self_reported_level=user.self_reported_level,
        onboarded=user.onboarded_at is not None,
        consent_version=user.consent_version,
        is_internal=user.is_internal,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


def _check_email(email: str) -> str:
    normalized = domain.normalize_email(email)
    if not _EMAIL.match(normalized) or len(normalized) > 255:
        raise ValidationFailed("Escribe un correo válido.", code="email_invalid")
    return normalized


def _check_password(password: str, confirm: str, email: str) -> None:
    problems = domain.password_problems(password, email)
    if problems:
        raise ValidationFailed(PASSWORD_MESSAGES[problems[0]], code=problems[0])
    if password != confirm:
        raise ValidationFailed("Las contraseñas no coinciden.", code="password_mismatch")


class IdentityService:
    def __init__(
        self,
        uow: UnitOfWorkFactory,
        clock: Clock,
        settings: Settings,
        passwords: Passwords,
        limiter: domain.SlidingWindowLimiter,
    ) -> None:
        self.uow = uow
        self.clock = clock
        self.settings = settings
        self.passwords = passwords
        self.limiter = limiter

    # -- sesiones -----------------------------------------------------------------------

    def _open_session(self, s: Session, user: User, now: datetime) -> tuple[str, str, datetime]:
        token = new_token()
        csrf = derive_csrf_token(token)
        window = domain.open_session_window(
            now, self.settings.session_absolute_days, self.settings.session_idle_hours
        )
        s.add(
            AuthSession(
                id=uuid.uuid4(),
                user_id=user.id,
                token_hash=hash_token(token),
                csrf_hash=hash_token(csrf),
                created_at=window.created_at,
                last_seen_at=window.last_seen_at,
                absolute_expires_at=window.absolute_expires_at,
                idle_expires_at=window.idle_expires_at,
            )
        )
        return token, csrf, window.absolute_expires_at

    def authenticate(self, session_token: str) -> AuthContext | None:
        now = self.clock.now()
        with self.uow() as s:
            row = repository.session_by_token_hash(s, hash_token(session_token))
            if row is None:
                return None
            window = domain.SessionWindow(
                created_at=row.created_at,
                last_seen_at=row.last_seen_at,
                absolute_expires_at=row.absolute_expires_at,
                idle_expires_at=row.idle_expires_at,
                revoked_at=row.revoked_at,
            )
            if not domain.session_is_active(window, now):
                return None
            refreshed = domain.refreshed_window(window, now, self.settings.session_idle_hours)
            if refreshed is not None:
                row.last_seen_at = refreshed.last_seen_at
                row.idle_expires_at = refreshed.idle_expires_at
            user = repository.user_by_id(s, row.user_id)
            if user is None:
                return None
            return AuthContext(
                user_id=user.id,
                role=user.role.value,
                session_id=row.id,
                csrf_hash=row.csrf_hash,
                is_internal=user.is_internal,
                timezone=user.timezone,
            )

    def session_is_active(self, session_id: uuid.UUID) -> bool:
        """Para conexiones largas (WebSocket de voz): ¿la sesión de la app sigue viva?"""
        now = self.clock.now()
        with self.uow() as s:
            row = s.get(AuthSession, session_id)
            if row is None:
                return False
            return domain.session_is_active(
                domain.SessionWindow(
                    row.created_at,
                    row.last_seen_at,
                    row.absolute_expires_at,
                    row.idle_expires_at,
                    row.revoked_at,
                ),
                now,
            )

    @staticmethod
    def csrf_matches(ctx: AuthContext, header_token: str | None) -> bool:
        if not header_token:
            return False
        return constant_time_equals(hash_token(header_token), ctx.csrf_hash)

    @staticmethod
    def csrf_for(session_token: str) -> str:
        return derive_csrf_token(session_token)

    def login(
        self, email: str, password: str, ip: str, previous_token: str | None = None
    ) -> IssuedSession:
        now = self.clock.now()
        normalized = domain.normalize_email(email)
        wait = self.limiter.hit((f"email:{normalized}", f"ip:{ip}"), now)
        if wait is not None:
            with self.uow() as s:
                limited = repository.user_by_email(s, normalized)
                ref = user_ref(limited.id, self.settings.log_salt) if limited else None
            logger.warning("login_rate_limited", extra={"retry_after": wait, "user_ref": ref})
            raise RateLimited(wait)
        with self.uow() as s:
            user = repository.user_by_email(s, normalized)
            if user is None:
                self.passwords.burn(password)
                raise InvalidCredentials()
            if not self.passwords.verify(user.password_hash, password):
                logger.info(
                    "login_failed", extra={"user_ref": user_ref(user.id, self.settings.log_salt)}
                )
                raise InvalidCredentials()
            if previous_token:
                previous = repository.session_by_token_hash(s, hash_token(previous_token))
                if previous is not None and previous.revoked_at is None:
                    previous.revoked_at = now
                    previous.revoke_reason = "rotated"
            user.last_login_at = now
            token, csrf, expires = self._open_session(s, user, now)
            s.flush()
            view = _view(user)
        logger.info("login", extra={"user_ref": user_ref(view.id, self.settings.log_salt)})
        return IssuedSession(token=token, csrf_token=csrf, expires_at=expires, user=view)

    def logout(self, session_id: uuid.UUID) -> None:
        now = self.clock.now()
        with self.uow() as s:
            row = s.get(AuthSession, session_id)
            if row is not None and row.revoked_at is None:
                row.revoked_at = now
                row.revoke_reason = "logout"

    # -- invitaciones -------------------------------------------------------------------

    def create_invitation(
        self, email: str, *, created_by: uuid.UUID | None, role: UserRole = UserRole.student
    ) -> IssuedLink:
        now = self.clock.now()
        normalized = _check_email(email)
        token = new_token()
        expires = now + timedelta(hours=self.settings.invitation_ttl_hours)
        with self.uow() as s:
            repository.lock_email(s, normalized)
            if repository.user_by_email(s, normalized) is not None:
                raise Conflict("Ya existe una cuenta con este correo.", code="email_taken")
            repository.expire_pending_invitations(s, normalized, now)
            s.add(
                Invitation(
                    id=uuid.uuid4(),
                    email=normalized,
                    role=role,
                    token_hash=hash_token(token),
                    created_by=created_by,
                    created_at=now,
                    expires_at=expires,
                )
            )
        logger.info("invitation_created", extra={"role": role.value})
        return IssuedLink(token=token, expires_at=expires, email=normalized)

    def inspect_invitation(self, token: str) -> tuple[str, datetime]:
        now = self.clock.now()
        with self.uow() as s:
            inv = repository.invitation_by_token_hash(s, hash_token(token))
            if inv is None or domain.one_time_token_status(
                inv.expires_at, inv.consumed_at, now
            ) != ("valid"):
                raise LinkInvalid()
            return inv.email, inv.expires_at

    def accept_invitation(
        self,
        *,
        token: str,
        password: str,
        password_confirm: str,
        accept_privacy: bool,
        consent_version: str,
        adult: bool,
        display_name: str | None,
    ) -> IssuedSession:
        try:
            return self._accept_invitation(
                token=token,
                password=password,
                password_confirm=password_confirm,
                accept_privacy=accept_privacy,
                consent_version=consent_version,
                adult=adult,
                display_name=display_name,
            )
        except IntegrityError as exc:
            # Dos invitaciones del mismo email aceptadas a la vez: gana una.
            raise LinkInvalid() from exc

    def _accept_invitation(
        self,
        *,
        token: str,
        password: str,
        password_confirm: str,
        accept_privacy: bool,
        consent_version: str,
        adult: bool,
        display_name: str | None,
    ) -> IssuedSession:
        now = self.clock.now()
        with self.uow() as s:
            inv = repository.invitation_by_token_hash(s, hash_token(token))
            if inv is None or domain.one_time_token_status(
                inv.expires_at, inv.consumed_at, now
            ) != ("valid"):
                raise LinkInvalid()
            if not accept_privacy or consent_version != self.settings.consent_version:
                raise ValidationFailed(
                    "Para continuar, lee y acepta el aviso de privacidad vigente.",
                    code="consent_required",
                )
            if not adult:
                raise ValidationFailed(
                    "El piloto es solo para personas mayores de edad.", code="adult_required"
                )
            _check_password(password, password_confirm, inv.email)
            if repository.user_by_email(s, inv.email) is not None:
                raise LinkInvalid()
            user = User(
                id=uuid.uuid4(),
                email=inv.email,
                password_hash=self.passwords.hash(password),
                role=inv.role,
                display_name=(display_name or "").strip() or None,
                consent_version=consent_version,
                consent_accepted_at=now,
                adult_attested_at=now,
                last_login_at=now,
            )
            s.add(user)
            s.flush()
            inv.consumed_at = now
            inv.consumed_user_id = user.id
            session_token, csrf, expires = self._open_session(s, user, now)
            s.flush()
            s.refresh(user)
            view = _view(user)
        logger.info(
            "invitation_accepted", extra={"user_ref": user_ref(view.id, self.settings.log_salt)}
        )
        return IssuedSession(token=session_token, csrf_token=csrf, expires_at=expires, user=view)

    # -- reset asistido -----------------------------------------------------------------

    def create_reset_link(self, user_id: uuid.UUID, *, created_by: uuid.UUID | None) -> IssuedLink:
        now = self.clock.now()
        token = new_token()
        expires = now + timedelta(hours=self.settings.reset_ttl_hours)
        with self.uow() as s:
            user = repository.user_by_id(s, user_id)
            if user is None:
                raise NotFound()
            repository.expire_pending_resets(s, user.id, now)
            s.add(
                PasswordResetToken(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    token_hash=hash_token(token),
                    created_by=created_by,
                    created_at=now,
                    expires_at=expires,
                )
            )
            email = user.email
        return IssuedLink(token=token, expires_at=expires, email=email)

    def reset_link_for_email(self, email: str) -> IssuedLink:
        with self.uow() as s:
            user = repository.user_by_email(s, domain.normalize_email(email))
            if user is None:
                raise NotFound("No existe una cuenta con ese correo.")
            user_id = user.id
        return self.create_reset_link(user_id, created_by=None)

    def inspect_reset(self, token: str) -> str:
        now = self.clock.now()
        with self.uow() as s:
            row = repository.reset_by_token_hash(s, hash_token(token))
            if row is None or domain.one_time_token_status(
                row.expires_at, row.consumed_at, now
            ) != ("valid"):
                raise LinkInvalid("Este enlace ya no sirve. Pide uno nuevo al equipo.")
            user = repository.user_by_id(s, row.user_id)
            if user is None:
                raise LinkInvalid("Este enlace ya no sirve. Pide uno nuevo al equipo.")
            return user.email

    def confirm_reset(self, token: str, password: str, password_confirm: str) -> IssuedSession:
        now = self.clock.now()
        with self.uow() as s:
            row = repository.reset_by_token_hash(s, hash_token(token))
            if row is None or domain.one_time_token_status(
                row.expires_at, row.consumed_at, now
            ) != ("valid"):
                raise LinkInvalid("Este enlace ya no sirve. Pide uno nuevo al equipo.")
            user = repository.user_by_id(s, row.user_id)
            if user is None:
                raise LinkInvalid("Este enlace ya no sirve. Pide uno nuevo al equipo.")
            _check_password(password, password_confirm, user.email)
            row.consumed_at = now
            user.password_hash = self.passwords.hash(password)
            repository.revoke_user_sessions(s, user.id, now, "password_reset")
            user.last_login_at = now
            session_token, csrf, expires = self._open_session(s, user, now)
            s.flush()
            view = _view(user)
        logger.info("password_reset", extra={"user_ref": user_ref(view.id, self.settings.log_salt)})
        return IssuedSession(token=session_token, csrf_token=csrf, expires_at=expires, user=view)

    # -- perfil -------------------------------------------------------------------------

    def get_me(self, user_id: uuid.UUID) -> UserView:
        with self.uow() as s:
            user = repository.user_by_id(s, user_id)
            if user is None:
                raise Unauthorized()
            return _view(user)

    def update_me(self, user_id: uuid.UUID, changes: dict[str, Any]) -> UserView:
        now = self.clock.now()
        with self.uow() as s:
            user = repository.user_by_id(s, user_id)
            if user is None:
                raise Unauthorized()
            for field, raw in changes.items():
                value = raw
                if field == "onboarded":
                    if value and user.onboarded_at is None:
                        user.onboarded_at = now
                    continue
                if field == "timezone":
                    if value is None:
                        continue
                    try:
                        ZoneInfo(value)
                    except (ZoneInfoNotFoundError, ValueError) as exc:
                        raise ValidationFailed(
                            "Elige una zona horaria válida.", code="timezone_invalid"
                        ) from exc
                if field == "display_name" and isinstance(value, str):
                    value = value.strip() or None
                if field not in _EDITABLE:
                    continue
                setattr(user, field, value)
            if user.target_exam != "other":
                user.target_exam_other = None
            s.flush()
            return _view(user)

    def export_me(self, user_id: uuid.UUID) -> dict[str, Any]:
        now = self.clock.now()
        with self.uow() as s:
            data = repository.export_rows(s, user_id)
        return {
            "exported_at": now.isoformat(),
            "format_version": 1,
            "tables": data,
        }

    def delete_me(self, user_id: uuid.UUID, password: str) -> None:
        with self.uow() as s:
            user = repository.user_by_id(s, user_id)
            if user is None:
                raise Unauthorized()
            if not self.passwords.verify(user.password_hash, password):
                raise ValidationFailed("La contraseña no es correcta.", code="password_incorrect")
            ref = user_ref(user.id, self.settings.log_salt)
            # Las invitaciones vencidas o reemplazadas guardan el email sin apuntar al
            # usuario: también se borran (no queda ninguna fila con sus datos).
            repository.delete_invitations_for_email(s, user.email)
            repository.delete_user(s, user.id)
        logger.info("account_deleted", extra={"user_ref": ref})

    # -- administración -----------------------------------------------------------------

    def list_users(self) -> list[AdminUserView]:
        now = self.clock.now()
        with self.uow() as s:
            users = repository.list_users(s)
            counts: dict[uuid.UUID, int] = {
                row[0]: int(row[1])
                for row in s.execute(
                    select(AuthSession.user_id, func.count())
                    .where(
                        AuthSession.revoked_at.is_(None),
                        AuthSession.absolute_expires_at > now,
                        AuthSession.idle_expires_at > now,
                    )
                    .group_by(AuthSession.user_id)
                )
            }
            return [AdminUserView(_view(u), int(counts.get(u.id, 0))) for u in users]

    def revoke_sessions(self, user_id: uuid.UUID) -> int:
        now = self.clock.now()
        with self.uow() as s:
            if repository.user_by_id(s, user_id) is None:
                raise NotFound()
            return repository.revoke_user_sessions(s, user_id, now, "admin")

    def set_internal(self, user_id: uuid.UUID, is_internal: bool) -> UserView:
        with self.uow() as s:
            user = repository.user_by_id(s, user_id)
            if user is None:
                raise NotFound()
            user.is_internal = is_internal
            s.flush()
            return _view(user)


_EDITABLE = frozenset(
    {
        "display_name",
        "timezone",
        "goal_purpose",
        "target_exam",
        "target_exam_other",
        "target_score",
        "target_date",
        "self_reported_level",
    }
)
