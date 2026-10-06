"""REQ-15/16 y ADR-14: feedback del producto, eventos de lista cerrada (solo ids y
enumerados), panel del piloto con cuentas internas excluidas (AC-23), triage de reportes,
errores 5xx registrados con retención de 30 días y guardas de rol."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.core.errors import ServiceUnavailable
from app.modules.insights import domain
from app.modules.insights.models import ErrorEvent, ProductEvent
from tests.helpers import Account, AccountFactory

L1 = "u1-l1-lectura"


def attempt(acct: Account, activity_id: str, selected: list[str]) -> None:
    res = acct.client.post(
        "/api/v1/attempts",
        json={"activity_id": activity_id, "response": {"selected": selected}},
        headers={**acct.headers(), "Idempotency-Key": str(uuid.uuid4())},
    )
    assert res.status_code == 201, res.text


def rate(acct: Account, item_id: str, rating: int, message: str = "") -> Any:
    return acct.client.post(
        "/api/v1/feedback",
        json={
            "context_type": "lesson",
            "context_id": item_id,
            "rating": rating,
            "message": message,
        },
        headers=acct.headers(),
    )


def test_events_are_a_closed_list_without_free_text() -> None:
    assert domain.clean_props("login", {"role": "student", "n": 2, "ok": True}) == {
        "role": "student",
        "n": 2,
        "ok": True,
    }
    with pytest.raises(domain.InvalidEvent):
        domain.clean_props("page_view", {})
    with pytest.raises(domain.InvalidEvent):
        domain.clean_props("feedback_submitted", {"message": "Me encantó la lección"})


def test_feedback_validation(student: Account, lesson: dict[str, Any]) -> None:
    item = lesson[L1]["item_id"]
    assert rate(student, item, 5, "Muy clara.").status_code == 201
    assert rate(student, item, 6).status_code == 422
    no_rating = student.client.post(
        "/api/v1/feedback",
        json={"context_type": "lesson", "context_id": item},
        headers=student.headers(),
    )
    assert no_rating.status_code == 422
    empty = student.client.post(
        "/api/v1/feedback",
        json={"context_type": "general", "page": "/ruta"},
        headers=student.headers(),
    )
    assert empty.status_code == 422
    general = student.client.post(
        "/api/v1/feedback",
        json={"context_type": "general", "message": "No encuentro mis repasos.", "page": "/inicio"},
        headers=student.headers(),
    )
    assert general.status_code == 201
    assert (
        student.client.post("/api/v1/feedback", json={"context_type": "general"}).status_code == 403
    )


def test_pilot_panel_excludes_internal_accounts(
    admin: Account, lesson: dict[str, Any], make_account: AccountFactory
) -> None:
    acts, item = lesson[L1]["activities"], lesson[L1]["item_id"]
    pilot = make_account("piloto@example.com")
    internal = make_account("equipo@example.com", is_internal=True)
    for acct in (pilot, internal):
        for key in ("u1.l1.p1", "u1.l1.p2", "u1.l1.p3", "u1.l1.p4"):
            attempt(acct, acts[key], ["a"])
    attempt(pilot, acts["u1.l1.p1"], ["b"])  # duplicado: 5 intentos del alumno del piloto
    rate(pilot, item, 4, "Me sirvió el ejemplo del horario.")
    rate(internal, item, 1, "Prueba interna.")

    res = admin.client.get("/api/v1/admin/pilot/summary", params={"days": 7})
    assert res.status_code == 200, res.text
    summary = res.json()
    assert summary["internal_excluded"] is True
    assert len(summary["active_by_day"]) == 8
    assert summary["active_by_day"][-1]["students"] == 1
    assert summary["attempts"] == 5
    assert summary["lessons_completed"] == 1
    assert summary["average_rating"] == 4.0 and summary["ratings"] == 1
    assert [c["email"] for c in summary["latest_comments"]] == ["piloto@example.com"]
    assert summary["reviews_due"] == 0 and summary["diagnostics"] == 0

    overview = admin.client.get("/api/v1/admin/feedback").json()
    assert overview["by_lesson"] == [
        {"item_id": item, "title": "Elegir un curso", "average": 4.0, "count": 1}
    ]
    assert {(f["email"], f["internal"]) for f in overview["latest"]} == {
        ("piloto@example.com", False),
        ("equipo@example.com", True),
    }


def test_admin_routes_are_guarded(student: Account, client: TestClient) -> None:
    for url in ("/api/v1/admin/pilot/summary", "/api/v1/admin/feedback", "/api/v1/admin/errors"):
        assert student.client.get(url).status_code == 403
        assert client.get(url).status_code == 401
    assert student.client.get("/api/v1/admin/content-reports").status_code == 403


def test_reports_are_triaged_and_emit_an_event(
    student: Account, admin: Account, lesson: dict[str, Any], db: Session
) -> None:
    rev, act = lesson[L1]["revision_id"], lesson[L1]["activities"]["u1.l1.p1"]
    res = student.client.post(
        "/api/v1/content-reports",
        json={"revision_id": rev, "activity_id": act, "category": "answer_key", "message": "?"},
        headers=student.headers(),
    )
    assert res.status_code == 201
    reports = admin.client.get("/api/v1/admin/content-reports", params={"status": "open"}).json()
    assert reports[0]["category"] == "answer_key" and reports[0]["item_title"]
    triaged = admin.client.patch(
        f"/api/v1/admin/content-reports/{reports[0]['id']}",
        json={"status": "resolved", "triage_note": "La clave es correcta; se aclaró la consigna."},
        headers=admin.headers(),
    )
    assert triaged.status_code == 200 and triaged.json()["status"] == "resolved"
    assert admin.client.get("/api/v1/admin/content-reports", params={"status": "open"}).json() == []
    event = db.scalars(select(ProductEvent).where(ProductEvent.name == "content_reported")).one()
    assert event.props == {"category": "answer_key"}


def test_flow_emits_closed_list_events(
    student: Account, lesson: dict[str, Any], db: Session
) -> None:
    acts, item = lesson[L1]["activities"], lesson[L1]["item_id"]
    student.client.get(f"/api/v1/lessons/{item}")
    student.client.post(
        "/api/v1/aids",
        json={"activity_id": acts["u1.l1.p1"], "kind": "hint", "index": 0},
        headers=student.headers(),
    )
    for key in ("u1.l1.p1", "u1.l1.p2", "u1.l1.p3", "u1.l1.p4"):
        attempt(student, acts[key], ["a"])
    rows = db.scalars(select(ProductEvent).where(ProductEvent.user_id == student.id)).all()
    names = [r.name for r in rows]
    assert names.count("login") == 1 and names.count("attempt_submitted") == 4
    assert {"lesson_started", "aid_used", "lesson_completed"} <= set(names)
    assert set(names) <= domain.EVENT_NAMES
    for row in rows:
        assert all(isinstance(v, bool | int) or len(str(v)) <= 64 for v in row.props.values())


def test_server_errors_are_recorded_and_old_ones_purged_at_startup(
    app: FastAPI, admin: Account, db: Session, clock: FakeClock
) -> None:
    def _boom() -> None:
        raise RuntimeError("detalle interno")

    def _busy() -> None:
        raise ServiceUnavailable("Ocupado.")

    app.router.add_api_route("/api/v1/_boom", _boom)
    app.router.add_api_route("/api/v1/_busy", _busy)
    app.router.routes.insert(0, app.router.routes.pop())
    app.router.routes.insert(0, app.router.routes.pop())
    with TestClient(app, base_url="https://testserver") as c:
        assert c.get("/api/v1/_boom").status_code == 500
        assert c.get("/api/v1/_busy").status_code == 503
    rows = {e.route: e for e in db.scalars(select(ErrorEvent)).all()}
    assert rows["/api/v1/_boom"].exception_type == "RuntimeError"
    assert rows["/api/v1/_boom"].error_code == "internal_error"
    assert rows["/api/v1/_busy"].status_code == 503
    listed = admin.client.get("/api/v1/admin/errors").json()
    assert {e["route"] for e in listed} == {"/api/v1/_boom", "/api/v1/_busy"}
    assert all("detalle" not in str(e) for e in listed)

    old = ErrorEvent(
        id=uuid.uuid4(),
        request_id="viejo",
        route="/api/v1/x",
        status_code=500,
        error_code="internal_error",
        occurred_at=clock.now() - timedelta(days=31),
    )
    db.add(old)
    db.flush()
    with TestClient(app, base_url="https://testserver"):
        pass  # el arranque limpia lo que pasó la retención
    db.expunge(old)
    assert db.scalar(select(ErrorEvent).where(ErrorEvent.id == old.id)) is None
    assert db.scalars(select(ErrorEvent)).all()
