"""`POST /content-reports`: ligado a una revisión publicada; solo propio en la exportación."""

from __future__ import annotations

from pathlib import Path

from tests.helpers import Account

BASE = "/api/v1/admin/content"


def _published_lesson(admin: Account) -> tuple[str, str]:
    rev = next(
        r for r in admin.client.get(f"{BASE}/revisions").json() if r["item_slug"] == "u1-l1-lectura"
    )
    admin.client.post(
        f"{BASE}/revisions/{rev['id']}/approve",
        json={"content_hash": rev["content_hash"]},
        headers=admin.headers(),
    )
    detail = admin.client.post(
        f"{BASE}/revisions/{rev['id']}/publish", json={}, headers=admin.headers()
    ).json()
    return rev["id"], detail["activities"][0]["id"]


def test_student_reports_a_problem(admin: Account, student: Account, imported: Path) -> None:
    rev_id, act_id = _published_lesson(admin)
    res = student.client.post(
        "/api/v1/content-reports",
        json={
            "revision_id": rev_id,
            "activity_id": act_id,
            "category": "answer_key",
            "message": "La opción B también parece correcta.",
        },
        headers=student.headers(),
    )
    assert res.status_code == 201
    export = student.client.get("/api/v1/me/export").json()
    assert export["tables"]["content_reports"][0]["category"] == "answer_key"


def test_reports_need_a_published_revision_and_valid_input(
    admin: Account, student: Account, imported: Path
) -> None:
    draft = next(
        r
        for r in admin.client.get(f"{BASE}/revisions").json()
        if r["item_slug"] == "u1-l3-escritura"
    )
    res = student.client.post(
        "/api/v1/content-reports",
        json={"revision_id": draft["id"], "category": "typo"},
        headers=student.headers(),
    )
    assert res.status_code == 404
    rev_id, _ = _published_lesson(admin)
    assert (
        student.client.post(
            "/api/v1/content-reports",
            json={"revision_id": rev_id, "category": "otra"},
            headers=student.headers(),
        ).status_code
        == 422
    )
    assert (
        student.client.post(
            "/api/v1/content-reports",
            json={"revision_id": rev_id, "category": "other", "message": "x" * 1001},
            headers=student.headers(),
        ).status_code
        == 422
    )
