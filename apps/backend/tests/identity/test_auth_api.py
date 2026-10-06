"""AC-05 (invitación, login, logout, reset), EDGE-01, EDGE-16 y cookie de sesión."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.bootstrap import Container
from app.core.clock import FakeClock
from app.modules.identity.models import AuthSession, Invitation, User
from tests.helpers import PASSWORD, Account, AccountFactory, login


def _token(url: str) -> str:
    match = re.search(r"#t=([A-Za-z0-9_-]+)$", url)
    assert match, url
    return match.group(1)


def _invite(admin: Account, email: str = "nueva@example.com") -> str:
    res = admin.client.post(
        "/api/v1/admin/invitations", json={"email": email}, headers=admin.headers()
    )
    assert res.status_code == 201, res.text
    assert res.json()["url"].startswith("http://localhost:5173/aceptar#t=")
    return _token(res.json()["url"])


def _accept(client: TestClient, token: str, container: Container, **over: object) -> Any:
    body = {
        "token": token,
        "password": "una frase segura",
        "password_confirm": "una frase segura",
        "accept_privacy": True,
        "consent_version": container.settings.consent_version,
        "adult": True,
        "display_name": "Ana",
    }
    body.update(over)
    return client.post("/api/v1/auth/invitations/accept", json=body)


def test_invitation_flow_creates_student_and_session(
    admin: Account, client: TestClient, container: Container, db: Session
) -> None:
    token = _invite(admin)
    info = client.post("/api/v1/auth/invitations/inspect", json={"token": token})
    assert info.json()["email"] == "nueva@example.com"
    assert info.json()["consent_version"] == container.settings.consent_version
    res = _accept(client, token, container)
    assert res.status_code == 201, res.text
    me = res.json()
    assert me["email"] == "nueva@example.com"
    assert me["role"] == "student"
    assert me["onboarded"] is False
    assert client.get("/api/v1/me").json()["id"] == me["id"]
    user = db.scalar(select(User).where(User.email == "nueva@example.com"))
    assert user is not None and user.consent_accepted_at and user.adult_attested_at


def test_invitation_is_single_use(admin: Account, client: TestClient, container: Container) -> None:
    token = _invite(admin)
    assert _accept(client, token, container).status_code == 201
    other = TestClient(
        client.app, base_url="https://testserver", headers={"Origin": "http://localhost:5173"}
    )
    again = _accept(other, token, container)
    assert again.status_code == 410
    assert again.json()["error"]["message"].startswith("Este enlace ya no sirve")


def test_invitation_expires(
    admin: Account, client: TestClient, container: Container, clock: FakeClock
) -> None:
    token = _invite(admin)
    clock.advance(timedelta(hours=72))
    assert client.post("/api/v1/auth/invitations/inspect", json={"token": token}).status_code == 410
    assert _accept(client, token, container).status_code == 410


def test_role_cannot_be_chosen(admin: Account, client: TestClient, container: Container) -> None:
    res = admin.client.post(
        "/api/v1/admin/invitations",
        json={"email": "x@example.com", "role": "admin"},
        headers=admin.headers(),
    )
    assert res.status_code == 422
    token = _invite(admin)
    assert _accept(client, token, container, role="admin").status_code == 422


def test_accept_requires_consent_adult_and_good_password(
    admin: Account, client: TestClient, container: Container
) -> None:
    token = _invite(admin)
    assert (
        _accept(client, token, container, accept_privacy=False).json()["error"]["code"]
        == "consent_required"
    )
    assert (
        _accept(client, token, container, consent_version="vieja").json()["error"]["code"]
        == "consent_required"
    )
    assert (
        _accept(client, token, container, adult=False).json()["error"]["code"] == "adult_required"
    )
    short = _accept(client, token, container, password="corta", password_confirm="corta")
    assert short.json()["error"]["code"] == "password_too_short"
    mismatch = _accept(client, token, container, password_confirm="otra frase segura")
    assert mismatch.json()["error"]["code"] == "password_mismatch"
    # Nada de lo anterior consumió la invitación.
    assert _accept(client, token, container).status_code == 201


def test_new_invitation_replaces_pending_one(
    admin: Account, client: TestClient, container: Container
) -> None:
    first = _invite(admin, "doble@example.com")
    second = _invite(admin, "doble@example.com")
    assert client.post("/api/v1/auth/invitations/inspect", json={"token": first}).status_code == 410
    assert _accept(client, second, container).status_code == 201


def test_cannot_invite_existing_account(admin: Account, student: Account) -> None:
    res = admin.client.post(
        "/api/v1/admin/invitations", json={"email": student.email.upper()}, headers=admin.headers()
    )
    assert res.status_code == 409


def test_login_sets_secure_host_cookie(make_account: AccountFactory, client: TestClient) -> None:
    acct = make_account("cookie@example.com")
    res = client.post(
        "/api/v1/auth/login", json={"email": "COOKIE@example.com ", "password": PASSWORD}
    )
    assert res.status_code == 200
    cookie = res.headers["set-cookie"]
    assert cookie.startswith("__Host-pcre_session=")
    for attr in ("HttpOnly", "Secure", "SameSite=lax", "Path=/", "Max-Age=604800"):
        assert attr.lower() in cookie.lower()
    assert "domain" not in cookie.lower()
    assert res.json()["csrf_token"]
    assert acct.email == "cookie@example.com"


def test_wrong_password_and_unknown_email_get_the_same_error(
    make_account: AccountFactory, client: TestClient
) -> None:
    make_account("real@example.com")
    a = client.post(
        "/api/v1/auth/login", json={"email": "real@example.com", "password": "mala contraseña"}
    )
    b = client.post(
        "/api/v1/auth/login", json={"email": "nadie@example.com", "password": "mala contraseña"}
    )
    assert a.status_code == b.status_code == 401
    assert a.json()["error"]["message"] == b.json()["error"]["message"]


def test_login_rate_limit(
    make_account: AccountFactory, client: TestClient, clock: FakeClock
) -> None:
    make_account("limite@example.com")
    for _ in range(5):
        client.post(
            "/api/v1/auth/login",
            json={"email": "limite@example.com", "password": "mala contraseña"},
        )
    res = client.post(
        "/api/v1/auth/login", json={"email": "limite@example.com", "password": PASSWORD}
    )
    assert res.status_code == 429
    assert int(res.headers["retry-after"]) >= 1
    assert res.json()["error"]["message"] == "Espera un momento antes de intentarlo de nuevo."
    clock.advance(timedelta(seconds=61))
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "limite@example.com", "password": PASSWORD}
        ).status_code
        == 200
    )


def test_logout_revokes_the_session(student: Account) -> None:
    assert student.client.get("/api/v1/me").status_code == 200
    res = student.client.post("/api/v1/auth/logout", headers=student.headers())
    assert res.status_code == 204
    assert (
        "Max-Age=0" in res.headers["set-cookie"] or "expires" in res.headers["set-cookie"].lower()
    )
    assert student.client.get("/api/v1/me").status_code == 401


def test_login_rotates_the_previous_session(student: Account, db: Session) -> None:
    old = student.client.cookies.get("__Host-pcre_session")
    login(student.client, student.email)
    new = student.client.cookies.get("__Host-pcre_session")
    assert old != new
    revoked = db.scalar(
        select(func.count())
        .select_from(AuthSession)
        .where(AuthSession.user_id == student.id, AuthSession.revoke_reason == "rotated")
    )
    assert revoked == 1


def test_session_idle_and_absolute_expiry(student: Account, clock: FakeClock) -> None:
    clock.advance(timedelta(hours=23))
    assert student.client.get("/api/v1/me").status_code == 200  # renueva la inactividad
    clock.advance(timedelta(hours=23))
    assert student.client.get("/api/v1/me").status_code == 200
    clock.advance(timedelta(hours=25))
    res = student.client.get("/api/v1/me")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "session_expired"


def test_session_absolute_limit(student: Account, clock: FakeClock) -> None:
    for _ in range(8):  # 160 h de actividad continua: la sesión sigue viva
        clock.advance(timedelta(hours=20))
        assert student.client.get("/api/v1/me").status_code == 200
    clock.advance(timedelta(hours=8))  # 168 h: vencimiento absoluto de 7 días
    assert student.client.get("/api/v1/me").status_code == 401


def test_reset_link_revokes_all_sessions(
    admin: Account, student: Account, client: TestClient, make_account: AccountFactory
) -> None:
    second_device = TestClient(
        client.app, base_url="https://testserver", headers={"Origin": "http://localhost:5173"}
    )
    login(second_device, student.email)
    res = admin.client.post(f"/api/v1/admin/users/{student.id}/reset-link", headers=admin.headers())
    assert res.status_code == 200
    token = _token(res.json()["url"])
    assert client.post("/api/v1/auth/password-reset/inspect", json={"token": token}).json() == {
        "email": student.email
    }
    confirm = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": token,
            "password": "nueva frase segura",
            "password_confirm": "nueva frase segura",
        },
    )
    assert confirm.status_code == 200, confirm.text
    assert student.client.get("/api/v1/me").status_code == 401
    assert second_device.get("/api/v1/me").status_code == 401
    assert client.get("/api/v1/me").status_code == 200  # sesión nueva
    again = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": token,
            "password": "otra frase segura",
            "password_confirm": "otra frase segura",
        },
    )
    assert again.status_code == 410
    login(
        TestClient(
            client.app, base_url="https://testserver", headers={"Origin": "http://localhost:5173"}
        ),
        student.email,
        "nueva frase segura",
    )


def test_admin_can_revoke_sessions_and_mark_internal(admin: Account, student: Account) -> None:
    res = admin.client.post(
        f"/api/v1/admin/users/{student.id}/revoke-sessions", headers=admin.headers()
    )
    assert res.status_code == 204
    assert student.client.get("/api/v1/me").status_code == 401
    patch = admin.client.patch(
        f"/api/v1/admin/users/{student.id}", json={"is_internal": True}, headers=admin.headers()
    )
    assert patch.status_code == 200 and patch.json()["is_internal"] is True
    users = admin.client.get("/api/v1/admin/users").json()
    row = next(u for u in users if u["email"] == student.email)
    assert row["is_internal"] is True and row["active_sessions"] == 0
    assert {"email", "created_at", "last_login_at", "is_internal"} <= row.keys()


def test_students_cannot_use_admin_routes(student: Account) -> None:
    assert student.client.get("/api/v1/admin/users").status_code == 403
    res = student.client.post(
        "/api/v1/admin/invitations", json={"email": "z@example.com"}, headers=student.headers()
    )
    assert res.status_code == 403
    assert res.json()["error"]["message"] == "Esta sección es para el equipo editorial."


def test_invitation_rows_store_only_hashes(admin: Account, db: Session) -> None:
    token = _invite(admin, "hash@example.com")
    inv = db.scalar(select(Invitation).where(Invitation.email == "hash@example.com"))
    assert inv is not None and inv.token_hash != token and token not in inv.token_hash


def test_accept_and_reset_set_the_same_secure_cookie(
    admin: Account, client: TestClient, container: Container, student: Account
) -> None:
    res = _accept(client, _invite(admin, "cookie2@example.com"), container)
    reset = admin.client.post(
        f"/api/v1/admin/users/{student.id}/reset-link", headers=admin.headers()
    )
    fresh = TestClient(
        client.app, base_url="https://testserver", headers={"Origin": "http://localhost:5173"}
    )
    confirm = fresh.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": _token(reset.json()["url"]),
            "password": "nueva frase segura",
            "password_confirm": "nueva frase segura",
        },
    )
    for response in (res, confirm):
        cookie = response.headers["set-cookie"].lower()
        assert cookie.startswith("__host-pcre_session=")
        for attr in ("httponly", "secure", "samesite=lax", "path=/"):
            assert attr in cookie
        assert "domain" not in cookie


def test_rate_limit_uses_the_last_forwarded_ip(
    make_account: AccountFactory, client: TestClient
) -> None:
    make_account("xff@example.com")
    for i in range(5):
        client.post(
            "/api/v1/auth/login",
            json={"email": f"otra{i}@example.com", "password": "mala contraseña"},
            headers={"X-Forwarded-For": f"10.0.0.{i}, 203.0.113.9"},
        )
    # Cambiar el primer valor (lo controla el cliente) no evade el límite por IP.
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "xff@example.com", "password": PASSWORD},
        headers={"X-Forwarded-For": "10.9.9.9, 203.0.113.9"},
    )
    assert res.status_code == 429
