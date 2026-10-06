"""AC-13: las métricas coinciden con un fixture controlado (números exactos), con
duplicados que no inflan avance ni racha. REQ-14 por la API: repaso vencido, reparación
inmediata y repaso reutilizado (`repeated`). `POST /api/test/clock` solo existe con el reloj
de prueba activo."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bootstrap import Container
from app.core.clock import FakeClock
from app.main import create_app
from app.modules.practice.models import Attempt
from tests.conftest import TEST_ORIGIN
from tests.helpers import Account

TEXT = (
    "Dear Ms. Rivera, I am writing to ask about the evening English classes. Could you tell me "
    "the days and the price per month? I work until five, so I can only study after six. "
    "Thank you for your help. Best regards, Ana"
)


def attempt(acct: Account, activity_id: str, response: dict[str, Any]) -> dict[str, Any]:
    res = acct.client.post(
        "/api/v1/attempts",
        json={"activity_id": activity_id, "response": response},
        headers={**acct.headers(), "Idempotency-Key": str(uuid.uuid4())},
    )
    assert res.status_code == 201, res.text
    body: dict[str, Any] = res.json()
    return body


def progress(acct: Account) -> dict[str, Any]:
    res = acct.client.get("/api/v1/me/progress")
    assert res.status_code == 200, res.text
    body: dict[str, Any] = res.json()
    return body


def test_metrics_match_a_controlled_fixture(
    student: Account, all_formats: dict[str, Any], clock: FakeClock
) -> None:
    l1 = all_formats["u1-l1-lectura"]["activities"]
    l2 = all_formats["u1-l2-escucha"]["activities"]
    l3 = all_formats["u1-l3-escritura"]["activities"]
    empty = progress(student)
    assert empty["initial_accuracy"] == {"correct": 0, "total": 0}  # "aún sin medición"
    assert empty["streak_days"] == 0 and empty["next_action"]["reason"] == "next"

    # Día 1 (5 oct, 9:00 en Ciudad de México): L1 completa con un duplicado.
    attempt(student, l1["u1.l1.p1"], {"selected": ["b"]})  # primer intento fallido
    attempt(student, l1["u1.l1.p1"], {"selected": ["a"]})  # duplicado: no cuenta otra vez
    attempt(student, l1["u1.l1.p2"], {"selected": ["a"]})
    student.client.post(
        "/api/v1/aids",
        json={"activity_id": l1["u1.l1.p3"], "kind": "hint", "index": 0},
        headers=student.headers(),
    )
    assert attempt(student, l1["u1.l1.p3"], {"selected": ["a"]})["aided"] is True
    done = attempt(student, l1["u1.l1.p4"], {"selected": ["b"]})
    assert done["lesson_completed"] is True
    attempt(student, l1["u1.l1.p4"], {"selected": ["a"]})  # otro duplicado ya completa

    # Día 2 (+25 h): L3 en curso con orden y correo autoevaluado; el repaso de U1.R vence.
    clock.advance(timedelta(hours=25))
    student.relogin()
    attempt(student, l3["u1.l3.p3"], {"order": ["I", "usually", "walk", "to work"]})
    writing = attempt(student, l3["u1.l3.p1"], {"text": TEXT})
    student.client.post(
        f"/api/v1/attempts/{writing['id']}/self-assessment",
        json={"scores": {"task": 2}},
        headers=student.headers(),
    )
    res = student.client.get("/api/v1/me/reviews/next")
    assert res.status_code == 200, res.text
    review = res.json()["review"]
    assert review["objective"] == "U1.R" and review["due"] is True
    assert review["repeated"] is False and review["activity"]["pool"] == "review"
    assert review["activity"]["key"] == "u1.l1.r1"
    attempt(student, review["activity"]["id"], {"selected": ["a"]})  # acierto sin ayudas

    # Día 4 (sin actividad el día 3): un envío en L2.
    clock.advance(timedelta(days=2))
    student.relogin()
    attempt(student, l2["u1.l2.p1"], {"selected": ["a"]})

    p = progress(student)
    assert p["advance"]["correct"] == 1 and p["advance"]["total"] == 4
    assert p["advance"]["units"] == [
        {"unit": "u1-informacion-decisiones", "title": "Unidad 1", "correct": 1, "total": 4}
    ]
    # Primeros intentos corregidos solos: L1 p1 ✗, p2 ✓, p3 ✓ (con ayuda), p4 ✗, L3 p3 ✓, L2 p1 ✓.
    assert p["initial_accuracy"] == {"correct": 4, "total": 6}
    assert p["delayed_recall"] == {"correct": 1, "total": 1}
    assert p["aids"] == {"hint": 1, "support_es": 0, "transcript": 0, "example": 0}
    assert p["production"]["writing"] == {"average": 2.0, "count": 1, "label": "autoevaluación"}
    assert p["production"]["speaking"]["count"] == 0
    assert [r["objective"] for r in p["to_reinforce"]] == ["U1.R"]
    assert p["streak_days"] == 1  # días 1, 2 y 4: el hueco del día 3 corta la racha
    assert p["reviews_due"] == 0  # el repaso acertado pasó a la etapa 1 (+3 días)
    assert p["next_action"]["kind"] == "lesson" and p["next_action"]["reason"] == "in_progress"
    assert p["next_action"]["item_id"] == all_formats["u1-l2-escucha"]["item_id"]

    reviews = student.client.get("/api/v1/me/reviews").json()
    assert reviews["due"] == [] and reviews["upcoming"][0]["stage"] == 1


def test_streak_counts_local_days_once(
    student: Account, all_formats: dict[str, Any], clock: FakeClock
) -> None:
    l1 = all_formats["u1-l1-lectura"]["activities"]
    for _ in range(3):  # tres envíos el mismo día cuentan una vez
        attempt(student, l1["u1.l1.p1"], {"selected": ["a"]})
    assert progress(student)["streak_days"] == 1
    clock.advance(timedelta(days=1))
    student.relogin()
    assert progress(student)["streak_days"] == 1  # hoy sin envío: sigue viva desde ayer
    attempt(student, l1["u1.l1.p2"], {"selected": ["a"]})
    assert progress(student)["streak_days"] == 2
    clock.advance(timedelta(days=2))
    student.relogin()
    assert progress(student)["streak_days"] == 0


def test_repair_now_and_repeated_reviews(
    student: Account, all_formats: dict[str, Any], clock: FakeClock, db: Session
) -> None:
    l1 = all_formats["u1-l1-lectura"]["activities"]
    attempt(student, l1["u1.l1.p1"], {"selected": ["b"]})
    assert student.client.get("/api/v1/me/reviews/next").json()["review"] is None  # no vence
    repair = student.client.get("/api/v1/me/reviews/next", params={"objective": "U1.R"}).json()
    assert repair["review"]["due"] is False  # reparación inmediata opcional
    assert (
        student.client.get("/api/v1/me/reviews/next", params={"objective": "nada"}).status_code
        == 422
    )

    clock.advance(timedelta(hours=25))

    student.relogin()
    seen = []
    for _ in range(4):  # las cuatro actividades de repaso de U1.R, sin repetir
        review = student.client.get("/api/v1/me/reviews/next", params={"objective": "U1.R"}).json()[
            "review"
        ]
        assert review["repeated"] is False
        seen.append(review["activity"]["key"])
        attempt(student, review["activity"]["id"], {"selected": ["a"]})
        clock.advance(timedelta(minutes=5))
    assert seen == ["u1.l1.r1", "u1.l1.r2", "u1.l1.r3", "u1.l1.r4"]
    again = student.client.get("/api/v1/me/reviews/next", params={"objective": "U1.R"}).json()[
        "review"
    ]
    assert again["repeated"] is True and again["activity"]["key"] == "u1.l1.r1"  # la más antigua
    body = attempt(student, again["activity"]["id"], {"selected": ["a"]})
    assert db.scalars(select(Attempt).where(Attempt.id == body["id"])).one().repeated is True
    assert progress(student)["delayed_recall"]["total"] == 4  # el reutilizado no cuenta


def test_test_clock_route_exists_only_with_the_test_clock(
    container: Container, client: TestClient
) -> None:
    assert client.post("/api/test/clock", json={"advance_hours": 1}).status_code == 404
    settings = container.settings.model_copy(update={"test_clock_enabled": True})
    clock = FakeClock()
    app = create_app(
        settings,
        container=container.__class__(
            settings=settings, uow=container.uow, clock=clock, passwords=container.passwords
        ),
    )
    with TestClient(app, base_url="https://testserver", headers={"Origin": TEST_ORIGIN}) as c:
        before = clock.now()
        res = c.post("/api/test/clock", json={"advance_hours": 24})
        assert res.status_code == 200
        assert clock.now() - before == timedelta(hours=24)
