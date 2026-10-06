"""AC-06 / NFR-01: aislamiento con dos cuentas en cada endpoint con datos de alumno.

`STUDENT_ENDPOINTS` lista los endpoints de alumno; cada change set agrega los suyos aquí
o en su propia prueba de aislamiento (con recursos creados por la cuenta A y pedidos por
la B, que debe recibir 404).
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.modules.content.models import ContentReport
from tests.helpers import Account, AccountFactory, start

# Endpoints cuyo resultado depende solo de la sesión (no reciben ids de recursos).
STUDENT_ENDPOINTS = ["/api/v1/me", "/api/v1/me/export"]


def test_each_account_only_sees_its_own_data(make_account: AccountFactory) -> None:
    a = make_account("a@example.com")
    b = make_account("b@example.com")
    for url in STUDENT_ENDPOINTS:
        body_a = a.client.get(url).text
        body_b = b.client.get(url).text
        assert a.email in body_a and b.email not in body_a, url
        assert b.email in body_b and a.email not in body_b, url
        assert str(a.id) not in body_b, url


def test_admin_user_routes_reject_students(make_account: AccountFactory) -> None:
    a = make_account("a2@example.com")
    b = make_account("b2@example.com")
    for method, url in (
        ("POST", f"/api/v1/admin/users/{a.id}/reset-link"),
        ("POST", f"/api/v1/admin/users/{a.id}/revoke-sessions"),
        ("PATCH", f"/api/v1/admin/users/{a.id}"),
    ):
        res = b.client.request(method, url, json={"is_internal": True}, headers=b.headers())
        assert res.status_code == 403, url


def _attempt(acct: Account, activity_id: str, response: dict[str, Any], **extra: Any) -> Any:
    return acct.client.post(
        "/api/v1/attempts",
        json={"activity_id": activity_id, "response": response, **extra},
        headers={**acct.headers(), "Idempotency-Key": str(uuid.uuid4())},
    )


def test_progress_reviews_and_path_state_are_isolated(
    make_account: AccountFactory, all_formats: dict[str, Any], clock: FakeClock
) -> None:
    """Hallazgo 3 del verificador de CS-12: endpoints de sesión con datos de práctica."""
    a, b = make_account("a@example.com"), make_account("b@example.com")
    acts = all_formats["u1-l1-lectura"]["activities"]
    a.client.post(
        "/api/v1/aids",
        json={"activity_id": acts["u1.l1.p2"], "kind": "hint", "index": 0},
        headers=a.headers(),
    )
    first = _attempt(a, acts["u1.l1.p1"], {"selected": ["b"]}).json()
    _attempt(a, acts["u1.l1.p2"], {"selected": ["a"]})
    clock.advance(timedelta(hours=25))
    a.relogin()
    b.relogin()
    pa = a.client.get("/api/v1/me/progress").json()
    pb = b.client.get("/api/v1/me/progress").json()
    assert pa["initial_accuracy"]["total"] == 2 and pa["reviews_due"] == 1
    assert pb["initial_accuracy"] == {"correct": 0, "total": 0}
    assert pb["reviews_due"] == 0 and pb["aids"]["hint"] == 0 and pb["to_reinforce"] == []
    assert b.client.get("/api/v1/me/reviews").json() == {"due": [], "upcoming": []}
    assert b.client.get("/api/v1/me/reviews/next").json()["review"] is None
    path_id = b.client.get("/api/v1/learning-paths").json()[0]["id"]
    states = {
        item["slug"]: item["state"]
        for unit in b.client.get(f"/api/v1/learning-paths/{path_id}").json()["units"]
        for item in unit["items"]
    }
    assert states["u1-l1-lectura"] == "not_started"
    export_b = b.client.get("/api/v1/me/export").text
    assert first["id"] not in export_b and str(a.id) not in export_b
    foreign = _attempt(b, acts["u1.l1.p1"], {"selected": ["a"]}, revision_of=first["id"])
    assert foreign.status_code == 404  # `revision_of` ajeno


def test_assessment_form_state_is_isolated(
    student: Account, forms: dict[str, Any], make_account: AccountFactory
) -> None:
    form = forms["u1-checkpoint"]
    run = start(student, form["id"]).json()
    other = make_account("otra@example.com")
    info = other.client.get(f"/api/v1/assessments/{form['id']}").json()
    assert info["runs"] == [] and info["open_run_id"] is None
    assert other.client.get(f"/api/v1/assessment-runs/{run['id']}").status_code == 404
    own = student.client.get(f"/api/v1/assessments/{form['id']}").json()
    assert own["open_run_id"] == run["id"]


def test_content_report_rejects_foreign_or_unknown_attempts(
    make_account: AccountFactory, lesson: dict[str, Any], db: Session
) -> None:
    """Hallazgo 4 del verificador de CS-12: un reporte solo se liga a un intento propio."""
    a, b = make_account("a@example.com"), make_account("b@example.com")
    l1 = lesson["u1-l1-lectura"]
    act = l1["activities"]["u1.l1.p1"]
    foreign = _attempt(a, act, {"selected": ["b"]}).json()["id"]
    own = _attempt(b, act, {"selected": ["b"]}).json()["id"]
    rev = b.client.get(f"/api/v1/lessons/{l1['item_id']}").json()["revision_id"]

    def report(attempt_id: str) -> int:
        return int(
            b.client.post(
                "/api/v1/content-reports",
                json={
                    "revision_id": rev,
                    "activity_id": act,
                    "attempt_id": attempt_id,
                    "category": "typo",
                    "message": "x",
                },
                headers=b.headers(),
            ).status_code
        )

    assert report(foreign) == 404
    assert report(str(uuid.uuid4())) == 404  # inexistente: 404, no 500
    assert report(own) == 201
    linked = db.scalar(
        select(func.count())
        .select_from(ContentReport)
        .where(ContentReport.attempt_id == uuid.UUID(foreign))
    )
    assert linked == 0
