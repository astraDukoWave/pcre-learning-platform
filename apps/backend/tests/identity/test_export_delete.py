"""REQ-06 y AC-22: exportación y borrado de cuenta; EDGE-14."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.bootstrap import Container
from app.db.base import Base
from app.modules.identity.data_registry import REGISTRY
from tests.helpers import Account, AccountFactory, save, start, submit


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


def test_delete_also_removes_old_invitations_with_the_email(
    admin: Account, db: Session, container: Container
) -> None:
    for _ in range(2):
        res = admin.client.post(
            "/api/v1/admin/invitations",
            json={"email": "borrame@example.com"},
            headers=admin.headers(),
        )
    token = re.search(r"#t=(.+)$", res.json()["url"]).group(1)  # type: ignore[union-attr]
    c = TestClient(
        admin.client.app, base_url="https://testserver", headers={"Origin": "http://localhost:5173"}
    )
    me = c.post(
        "/api/v1/auth/invitations/accept",
        json={
            "token": token,
            "password": "una frase segura",
            "password_confirm": "una frase segura",
            "accept_privacy": True,
            "consent_version": container.settings.consent_version,
            "adult": True,
        },
    ).json()
    res = c.request(
        "DELETE",
        "/api/v1/me",
        json={"password": "una frase segura"},
        headers={"X-CSRF-Token": me["csrf_token"]},
    )
    assert res.status_code == 204
    for name, table in Base.metadata.tables.items():
        if "email" in table.c:
            count = db.scalar(
                select(func.count())
                .select_from(table)
                .where(table.c.email == "borrame@example.com")
            )
            assert count == 0, f"quedó el email en {name}"


def _rows_left(db: Session, user_id: uuid.UUID) -> dict[str, int]:
    left = {}
    for name, entry in REGISTRY.items():
        table = Base.metadata.tables[name]
        for column in entry.user_columns:
            n = db.scalar(select(func.count()).select_from(table).where(table.c[column] == user_id))
            if n:
                left[f"{name}.{column}"] = int(n)
    return left


def _delete(student: Account) -> None:
    res = student.client.request(
        "DELETE", "/api/v1/me", json={"password": student.password}, headers=student.headers()
    )
    assert res.status_code == 204


def test_delete_after_real_activity_leaves_no_rows(
    student: Account, all_formats: dict[str, Any], db: Session
) -> None:
    """AC-22 con actividad real (observación 2 del verificador de CS-12): progreso, ayudas,
    intentos, repaso, idempotencia, autoevaluación, valoración, reporte y eventos."""
    l1 = all_formats["u1-l1-lectura"]
    write = all_formats["u1-l3-escritura"]["activities"]["u1.l3.p1"]
    student.client.get(f"/api/v1/lessons/{l1['item_id']}")
    student.client.post(
        "/api/v1/aids",
        json={"activity_id": l1["activities"]["u1.l1.p1"], "kind": "hint", "index": 0},
        headers=student.headers(),
    )
    for activity, response in (
        (l1["activities"]["u1.l1.p1"], {"selected": ["b"]}),
        (write, {"text": " ".join(["word"] * 40)}),
    ):
        res = student.client.post(
            "/api/v1/attempts",
            json={"activity_id": activity, "response": response},
            headers={**student.headers(), "Idempotency-Key": str(uuid.uuid4())},
        )
        assert res.status_code == 201, res.text
    student.client.post(
        f"/api/v1/attempts/{res.json()['id']}/self-assessment",
        json={"scores": {"task": 2}},
        headers=student.headers(),
    )
    student.client.post(
        "/api/v1/feedback",
        json={"context_type": "lesson", "context_id": l1["item_id"], "rating": 4, "message": "x"},
        headers=student.headers(),
    )
    rev = student.client.get(f"/api/v1/lessons/{l1['item_id']}").json()["revision_id"]
    report = student.client.post(
        "/api/v1/content-reports",
        json={"revision_id": rev, "category": "typo", "message": "coma"},
        headers=student.headers(),
    )
    assert report.status_code == 201, report.text
    before = _rows_left(db, student.id)
    assert len(before) >= 8, before
    _delete(student)
    db.expire_all()
    assert _rows_left(db, student.id) == {}


def test_delete_after_an_assessment_run_leaves_no_rows(
    student: Account, forms: dict[str, Any], db: Session
) -> None:
    form = forms["u1-checkpoint"]
    run = start(student, form["id"]).json()
    save(student, run["id"], form["activities"]["u1.cp.a1"], {"selected": ["a"]})
    submit(student, run["id"])
    assert "assessment_runs.user_id" in _rows_left(db, student.id)
    _delete(student)
    db.expire_all()
    assert _rows_left(db, student.id) == {}
