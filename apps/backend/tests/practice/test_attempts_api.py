"""AC-09 (idempotencia), AC-12 (intento + repaso en una transacción), REQ-11 (ayudas del
servidor), EDGE-04/05 (revisión fijada y retiro) y aislamiento (AC-06)."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.modules.practice.models import Attempt, IdempotencyRecord, ServedAid
from app.modules.progress.models import ReviewSchedule
from tests.helpers import Account, AccountFactory

L1 = "u1-l1-lectura"


def post_attempt(
    acct: Account, activity_id: str, selected: list[str], key: str | None = None
) -> Any:
    return acct.client.post(
        "/api/v1/attempts",
        json={"activity_id": activity_id, "response": {"selected": selected}},
        headers={**acct.headers(), "Idempotency-Key": key or str(uuid.uuid4())},
    )


def count(db: Session, model: Any, **where: Any) -> int:
    stmt = select(func.count()).select_from(model)
    for k, v in where.items():
        stmt = stmt.where(getattr(model, k) == v)
    return int(db.scalar(stmt) or 0)


def test_correct_attempt_returns_feedback_after_submit(
    student: Account, lesson: dict[str, Any]
) -> None:
    act = lesson[L1]["activities"]["u1.l1.p1"]
    res = post_attempt(student, act, ["a"])
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["correct"] is True and body["mode"] == "practice" and body["first_attempt"] is True
    assert body["feedback"]["explanation"] == "Marta puede estudiar entre semana por la noche."
    assert body["result"]["correct_options"] == ["a"]
    assert body["review_objectives"] == []


def test_same_key_same_body_returns_same_result_and_one_row(
    student: Account, lesson: dict[str, Any], db: Session
) -> None:
    act = lesson[L1]["activities"]["u1.l1.p2"]
    key = str(uuid.uuid4())
    first = post_attempt(student, act, ["b"], key)
    second = post_attempt(student, act, ["b"], key)
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert second.headers.get("idempotent-replayed") == "true"
    assert count(db, Attempt, user_id=student.id) == 1


def test_same_key_different_body_is_409(
    student: Account, lesson: dict[str, Any], db: Session
) -> None:
    act = lesson[L1]["activities"]["u1.l1.p2"]
    key = str(uuid.uuid4())
    assert post_attempt(student, act, ["b"], key).status_code == 201
    res = post_attempt(student, act, ["a"], key)
    assert res.status_code == 409 and res.json()["error"]["code"] == "idempotency_conflict"
    assert count(db, Attempt, user_id=student.id) == 1


def test_idempotency_key_is_required(student: Account, lesson: dict[str, Any]) -> None:
    act = lesson[L1]["activities"]["u1.l1.p1"]
    res = student.client.post(
        "/api/v1/attempts",
        json={"activity_id": act, "response": {"selected": ["a"]}},
        headers=student.headers(),
    )
    assert res.status_code == 422
    bad = post_attempt(student, act, ["a"], key="no-es-uuid")
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "idempotency_key"


def test_body_cannot_carry_user_mode_or_score(student: Account, lesson: dict[str, Any]) -> None:
    act = lesson[L1]["activities"]["u1.l1.p1"]
    for extra in ({"user_id": str(uuid.uuid4())}, {"mode": "assessment"}, {"score": 1}):
        res = student.client.post(
            "/api/v1/attempts",
            json={"activity_id": act, "response": {"selected": ["a"]}, **extra},
            headers={**student.headers(), "Idempotency-Key": str(uuid.uuid4())},
        )
        assert res.status_code == 422


def test_invalid_response_shape_is_422_and_writes_nothing(
    student: Account, lesson: dict[str, Any], db: Session
) -> None:
    act = lesson[L1]["activities"]["u1.l1.p1"]
    res = post_attempt(student, act, ["z"])
    assert res.status_code == 422 and res.json()["error"]["code"] == "response_invalid"
    assert count(db, Attempt, user_id=student.id) == 0
    assert count(db, IdempotencyRecord, user_id=student.id) == 0


def test_first_failure_schedules_review_and_aids_mark_the_attempt(
    student: Account, lesson: dict[str, Any], db: Session
) -> None:
    act = lesson[L1]["activities"]["u1.l1.p3"]
    hint = student.client.post(
        "/api/v1/aids",
        json={"activity_id": act, "kind": "hint", "index": 0},
        headers=student.headers(),
    )
    assert hint.status_code == 200
    assert hint.json() == {
        "kind": "hint",
        "index": 0,
        "content": "Busca los días de cada curso.",
        "remaining": 0,
    }
    assert count(db, ServedAid, user_id=student.id) == 1
    res = post_attempt(student, act, ["c"])
    body = res.json()
    assert body["correct"] is False and body["aided"] is True
    assert body["review_objectives"] == ["U1.R"]
    review = db.scalar(select(ReviewSchedule).where(ReviewSchedule.user_id == student.id))
    assert review is not None and review.stage == 0
    aid = db.scalar(select(ServedAid).where(ServedAid.user_id == student.id))
    assert aid is not None and str(aid.attempt_id) == body["id"]
    retry = post_attempt(student, act, ["a"]).json()
    assert retry["first_attempt"] is False and retry["aided"] is False


def test_unknown_aid_kind_or_index(student: Account, lesson: dict[str, Any]) -> None:
    act = lesson[L1]["activities"]["u1.l1.p1"]
    res = student.client.post(
        "/api/v1/aids",
        json={"activity_id": act, "kind": "hint", "index": 3},
        headers=student.headers(),
    )
    assert res.status_code == 404
    res = student.client.post(
        "/api/v1/aids", json={"activity_id": act, "kind": "transcript"}, headers=student.headers()
    )
    assert res.status_code == 404


def test_assessment_items_refuse_aids_and_direct_attempts(
    student: Account, lesson: dict[str, Any]
) -> None:
    act = lesson["u1-checkpoint"]["activities"]["u1.cp.a1"]
    aid = student.client.post(
        "/api/v1/aids", json={"activity_id": act, "kind": "hint"}, headers=student.headers()
    )
    assert aid.status_code == 403 and aid.json()["error"]["code"] == "assessment_mode"
    assert post_attempt(student, act, ["a"]).status_code == 403


def test_lesson_completes_when_every_practice_activity_was_sent(
    student: Account, lesson: dict[str, Any]
) -> None:
    acts = lesson[L1]["activities"]
    item = lesson[L1]["item_id"]
    student.client.get(f"/api/v1/lessons/{item}")
    for i in range(1, 4):
        assert post_attempt(student, acts[f"u1.l1.p{i}"], ["b"]).json()["lesson_completed"] is False
    assert post_attempt(student, acts["u1.l1.p4"], ["b"]).json()["lesson_completed"] is True
    path_id = student.client.get("/api/v1/learning-paths").json()[0]["id"]
    path = student.client.get(f"/api/v1/learning-paths/{path_id}").json()
    states = {i["slug"]: i["state"] for u in path["units"] for i in u["items"]}
    assert states[L1] == "completed"


def test_lesson_resumes_with_last_attempts(
    student: Account, lesson: dict[str, Any], clock: FakeClock
) -> None:
    item, act = lesson[L1]["item_id"], lesson[L1]["activities"]["u1.l1.p1"]
    student.client.get(f"/api/v1/lessons/{item}")
    post_attempt(student, act, ["b"])
    # Dos envíos reales nunca comparten instante; con el reloj falso hay que avanzarlo o el
    # "último" queda empatado y el orden lo decide PostgreSQL.
    clock.advance(timedelta(seconds=30))
    post_attempt(student, act, ["a"])
    dto = student.client.get(f"/api/v1/lessons/{item}").json()
    assert dto["last_attempts"][act]["response"] == {"selected": ["a"]}
    assert dto["progress"]["started_at"] and dto["progress"]["completed_at"] is None


def test_attempt_and_review_are_one_transaction(
    student: Account, lesson: dict[str, Any], db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-12: una falla provocada después del insert revierte intento, repaso e idempotencia."""
    from app.modules.practice import service as practice_service

    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("falla provocada después del insert")

    monkeypatch.setattr(practice_service.PracticeService, "_update_lesson_progress", boom)
    act = lesson[L1]["activities"]["u1.l1.p4"]
    res = post_attempt(student, act, ["c"])
    assert res.status_code == 500
    assert count(db, Attempt, user_id=student.id) == 0
    assert count(db, ReviewSchedule, user_id=student.id) == 0
    assert count(db, IdempotencyRecord, user_id=student.id) == 0


def test_withdrawn_pinned_lesson_is_released_and_history_kept(
    student: Account, admin: Account, lesson: dict[str, Any], db: Session
) -> None:
    item, act = lesson[L1]["item_id"], lesson[L1]["activities"]["u1.l1.p1"]
    student.client.get(f"/api/v1/lessons/{item}")
    attempt_id = post_attempt(student, act, ["a"]).json()["id"]
    admin.client.post(
        f"/api/v1/admin/content/revisions/{lesson[L1]['revision_id']}/withdraw",
        json={"reason": "Clave en revisión"},
        headers=admin.headers(),
    )
    res = student.client.get(f"/api/v1/lessons/{item}")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "lesson_withdrawn"
    assert "se retiró para corregirla" in res.json()["error"]["message"]
    assert post_attempt(student, act, ["a"]).status_code == 404  # bloquea intentos nuevos
    assert student.client.get(f"/api/v1/attempts/{attempt_id}").status_code == 200
    path_id = student.client.get("/api/v1/learning-paths").json()[0]["id"]
    slugs = {
        i["slug"]
        for u in student.client.get(f"/api/v1/learning-paths/{path_id}").json()["units"]
        for i in u["items"]
    }
    assert L1 not in slugs


def test_attempts_are_isolated_between_accounts(
    make_account: AccountFactory, lesson: dict[str, Any]
) -> None:
    a, b = make_account("a@example.com"), make_account("b@example.com")
    item, act = lesson[L1]["item_id"], lesson[L1]["activities"]["u1.l1.p1"]
    attempt_id = post_attempt(a, act, ["a"]).json()["id"]
    assert b.client.get(f"/api/v1/attempts/{attempt_id}").status_code == 404
    assert b.client.get("/api/v1/me/attempts").json() == []
    assert [x["id"] for x in a.client.get("/api/v1/me/attempts").json()] == [attempt_id]
    assert b.client.get(f"/api/v1/lessons/{item}").json()["last_attempts"] == {}
    # La misma clave en otra cuenta es otra operación.
    key = str(uuid.uuid4())
    assert post_attempt(a, act, ["b"], key).status_code == 201
    assert post_attempt(b, act, ["b"], key).json()["first_attempt"] is True
