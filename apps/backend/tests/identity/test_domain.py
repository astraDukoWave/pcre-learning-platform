from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core.security import Passwords, derive_csrf_token, hash_token, new_token
from app.modules.identity import domain

NOW = datetime(2026, 10, 5, 15, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("password", "problems"),
    [
        ("123456789", ["password_too_short"]),
        ("a" * 10, []),
        ("a" * 128, []),
        ("a" * 129, ["password_too_long"]),
        ("Ana@Example.com", ["password_equals_email"]),
        ("frase larga sin reglas raras", []),
    ],
)
def test_password_policy(password: str, problems: list[str]) -> None:
    assert domain.password_problems(password, "ana@example.com") == problems


def test_tokens_are_random_and_only_their_hash_is_stored() -> None:
    a, b = new_token(), new_token()
    assert a != b and len(a) >= 43
    assert hash_token(a) != a and len(hash_token(a)) == 64
    assert derive_csrf_token(a) == derive_csrf_token(a) != derive_csrf_token(b)


def test_argon2id_hash_and_verify() -> None:
    pw = Passwords(fast=True)
    h = pw.hash("correct horse battery")
    assert h.startswith("$argon2id$")
    assert pw.verify(h, "correct horse battery")
    assert not pw.verify(h, "wrong horse battery")
    assert not pw.verify("not-a-hash", "x")


def test_session_absolute_and_idle_expiry() -> None:
    w = domain.open_session_window(NOW, absolute_days=7, idle_hours=24)
    assert domain.session_is_active(w, NOW + timedelta(hours=23))
    assert not domain.session_is_active(w, NOW + timedelta(hours=24))
    # Actividad cada 20 h la mantiene viva... hasta el vencimiento absoluto de 7 días.
    t = NOW
    for _ in range(9):
        t += timedelta(hours=20)
        refreshed = domain.refreshed_window(w, t, 24)
        if refreshed is not None and domain.session_is_active(w, t):
            w = refreshed
    assert not domain.session_is_active(w, NOW + timedelta(days=7))


def test_last_seen_is_written_at_most_every_five_minutes() -> None:
    w = domain.open_session_window(NOW, 7, 24)
    assert domain.refreshed_window(w, NOW + timedelta(minutes=4), 24) is None
    assert domain.refreshed_window(w, NOW + timedelta(minutes=5), 24) is not None


def test_revoked_session_is_inactive() -> None:
    w = domain.open_session_window(NOW, 7, 24)
    revoked = domain.SessionWindow(
        w.created_at, w.last_seen_at, w.absolute_expires_at, w.idle_expires_at, NOW
    )
    assert not domain.session_is_active(revoked, NOW + timedelta(minutes=1))


@pytest.mark.parametrize(
    ("expires", "consumed", "status"),
    [
        (NOW + timedelta(hours=1), None, "valid"),
        (NOW, None, "expired"),
        (NOW + timedelta(hours=1), NOW, "consumed"),
    ],
)
def test_one_time_token_status(expires: datetime, consumed: datetime | None, status: str) -> None:
    assert domain.one_time_token_status(expires, consumed, NOW) == status


def test_rate_limiter_per_minute_and_hour() -> None:
    lim = domain.SlidingWindowLimiter(((5, 60), (20, 3600)))
    t = NOW
    for _ in range(5):
        assert lim.hit(("email:a",), t) is None
    wait = lim.hit(("email:a",), t)
    assert wait is not None and 1 <= wait <= 61
    assert lim.hit(("email:b",), t) is None  # otra clave no se afecta
    t += timedelta(seconds=61)
    assert lim.hit(("email:a",), t) is None
    # 20 por hora
    lim2 = domain.SlidingWindowLimiter(((5, 60), (20, 3600)))
    t = NOW
    for i in range(20):
        assert lim2.hit(("ip:1",), t + timedelta(minutes=2 * i)) is None
    assert lim2.hit(("ip:1",), t + timedelta(minutes=41)) is not None
