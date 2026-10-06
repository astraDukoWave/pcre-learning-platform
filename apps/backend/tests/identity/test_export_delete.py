"""REQ-06 y AC-22: exportación y borrado de cuenta; EDGE-14."""

from __future__ import annotations

import json
import re

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.bootstrap import Container
from app.db.base import Base
from app.modules.identity.data_registry import REGISTRY
from tests.helpers import Account, AccountFactory


def test_export_contains_only_own_data_without_secrets(
    student: Account, make_account: AccountFactory
) -> None:
    other = make_account("otra@example.com")
    res = student.client.get("/api/v1/me/export")
    assert res.status_code == 200
    assert "attachment" in res.headers["content-disposition"]
    data = res.json()
    users = data["tables"]["users"]
    assert [u["email"] for u in users] == [student.email]
    assert "password_hash" not in users[0]
    sessions = data["tables"]["auth_sessions"]
    assert sessions and all("token_hash" not in s and "csrf_hash" not in s for s in sessions)
    raw = json.dumps(data)
    assert other.email not in raw
    assert str(other.id) not in raw
    assert student.csrf not in raw


def test_delete_requires_the_password(student: Account) -> None:
    res = student.client.request(
        "DELETE", "/api/v1/me", json={"password": "no es la mía"}, headers=student.headers()
    )
    assert res.status_code == 422
    assert student.client.get("/api/v1/me").status_code == 200


def test_delete_removes_every_row_and_allows_reinvite(
    student: Account, admin: Account, db: Session, container: Container
) -> None:
    res = student.client.request(
        "DELETE", "/api/v1/me", json={"password": student.password}, headers=student.headers()
    )
    assert res.status_code == 204
    assert "__Host-pcre_session" in res.headers["set-cookie"]
    assert student.client.get("/api/v1/me").status_code == 401
    for name, entry in REGISTRY.items():
        table = Base.metadata.tables[name]
        for column in entry.user_columns:
            count = db.scalar(
                select(func.count()).select_from(table).where(table.c[column] == student.id)
            )
            assert count == 0, f"quedaron filas en {name}.{column}"
    res = admin.client.post(
        "/api/v1/admin/invitations", json={"email": student.email}, headers=admin.headers()
    )
    assert res.status_code == 201
    token = re.search(r"#t=(.+)$", res.json()["url"]).group(1)  # type: ignore[union-attr]
    fresh = TestClient(
        student.client.app,
        base_url="https://testserver",
        headers={"Origin": "http://localhost:5173"},
    )
    accepted = fresh.post(
        "/api/v1/auth/invitations/accept",
        json={
            "token": token,
            "password": "una frase segura",
            "password_confirm": "una frase segura",
            "accept_privacy": True,
            "consent_version": container.settings.consent_version,
            "adult": True,
        },
    )
    assert accepted.status_code == 201
