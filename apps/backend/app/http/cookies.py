"""Cookie de sesión `__Host-pcre_session`: HttpOnly, Secure, SameSite=Lax, Path=/, sin Domain."""

from __future__ import annotations

from datetime import datetime

from fastapi import Response

SESSION_COOKIE = "__Host-pcre_session"


def set_session_cookie(response: Response, token: str, expires_at: datetime, now: datetime) -> None:
    max_age = max(0, int((expires_at - now).total_seconds()))
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="lax")
