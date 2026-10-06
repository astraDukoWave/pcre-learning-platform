"""Primitivas de seguridad: tokens opacos, hash de tokens, CSRF derivado y Argon2id.

Sin criptografía propia (`docs/arquitectura.md` §7): `secrets`, `hashlib`, `hmac` y
`argon2-cffi` con sus parámetros por defecto.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_CSRF_LABEL = b"pcre-csrf-v1"


def new_token() -> str:
    """32 bytes aleatorios en base64 url-safe (sesiones, invitaciones y resets)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """En la base solo se guarda el sha256 del token."""
    return hashlib.sha256(token.encode()).hexdigest()


def derive_csrf_token(session_token: str) -> str:
    """El token CSRF se deriva del token de sesión: `GET /me` lo puede volver a entregar
    sin guardarlo en claro (en la base solo va su hash)."""
    return hmac.new(session_token.encode(), _CSRF_LABEL, hashlib.sha256).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


class Passwords:
    """Argon2id. `fast=True` solo en pruebas (mismo algoritmo, menos costo)."""

    def __init__(self, *, fast: bool = False) -> None:
        self._hasher = (
            PasswordHasher(time_cost=1, memory_cost=8, parallelism=1) if fast else PasswordHasher()
        )
        self._dummy = self._hasher.hash("pcre-dummy-password-for-timing")

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    def burn(self, password: str) -> None:
        """Iguala el tiempo de respuesta cuando el email no existe."""
        self.verify(self._dummy, password)
