"""MVP-02 REQ-02 de extremo a extremo con el evaluador falso: AC-04 (idempotencia del
feedback y política de `unknown`), `failed` reintentable, abstención, aislamiento, AC-02
(parte backend: 503 sin capacidad ni presupuesto) y 👍/👎 por observación."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.bootstrap import Container
from app.core.clock import FakeClock
from app.core.config import Settings
from app.db.uow import UnitOfWorkFactory
from app.modules.coaching.feedback.adapters.fake import FakeFeedbackEvaluator
from app.modules.insights.models import ErrorEvent, ProductEvent, UserFeedback
from app.modules.practice.models import Attempt
from app.modules.progress.models import ReviewSchedule
from app.modules.usage.models import AiRun, BudgetPeriod
from tests.conftest import FAST_PASSWORDS
from tests.helpers import Account, AccountFactory

FUNDED = {
    "ai_feedback_enabled": True,
    "budget_global_monthly_microusd": 5_000_000,
    "budget_user_monthly_microusd": 1_000_000,
    "gemini_price_input_per_mtok_microusd": 100_000,
    "gemini_price_output_per_mtok_microusd": 400_000,
    "feedback_provider": "fake",
}
TEXT = (
    "Dear Northside, I am writing to ask about your evening English classes. Could you tell me "
    "which days the classes meet? I would also like to know the price per month. Thank you."
)


@pytest.fixture
def evaluator() -> FakeFeedbackEvaluator:
    return FakeFeedbackEvaluator()


@pytest.fixture
def container(
    settings: Settings, uow: UnitOfWorkFactory, clock: FakeClock, evaluator: FakeFeedbackEvaluator
) -> Container:
    return Container(
        settings=settings.model_copy(update=FUNDED),
        uow=uow,
        clock=clock,
        passwords=FAST_PASSWORDS,
        feedback_evaluator=evaluator,
        ready_providers=frozenset({"ai_feedback"}),
    )


def write(acct: Account, all_formats: dict[str, Any], text: str = TEXT) -> str:
    act = all_formats["u1-l3-escritura"]["activities"]["u1.l3.p1"]
    res = acct.client.post(
        "/api/v1/attempts",
        json={"activity_id": act, "response": {"text": text}},
        headers={**acct.headers(), "Idempotency-Key": str(uuid.uuid4())},
    )
    assert res.status_code == 201, res.text
    return str(res.json()["id"])


def ask(acct: Account, attempt_id: str, key: str | None = None) -> Any:
    return acct.client.post(
        f"/api/v1/attempts/{attempt_id}/feedback",
        headers={**acct.headers(), "Idempotency-Key": key or str(uuid.uuid4())},
    )


def count(db: Session, model: Any, *where: Any) -> int:
    return int(db.scalar(select(func.count()).select_from(model).where(*where)) or 0)


def user_budget(db: Session, user_id: uuid.UUID) -> tuple[int, int]:
    row = db.scalars(select(BudgetPeriod).where(BudgetPeriod.user_id == user_id)).one()
    db.refresh(row)
    return row.reserved_microusd, row.spent_microusd


def test_feedback_with_literal_evidence_is_saved_and_schedules_a_review(
    student: Account, all_formats: dict[str, Any], db: Session, evaluator: FakeFeedbackEvaluator
) -> None:
    attempt_id = write(student, all_formats)
    res = ask(student, attempt_id, key="11111111-1111-4111-8111-111111111111")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "evaluable" and body["label"] == "Feedback automático orientativo (IA)"
    (obs,) = body["observations"]
    assert obs["criterion"] == "task" and obs["criterion_name_es"] == "Tarea"
    assert obs["evidence"].lower() in TEXT.lower()
    run = db.get(AiRun, uuid.UUID(body["run_id"]))
    assert run is not None and run.status == "succeeded" and run.cost_microusd
    assert run.prompt_version == "writing-v1" and run.attempt_id == uuid.UUID(attempt_id)
    reserved, spent = user_budget(db, student.id)
    assert reserved == 0 and spent == run.cost_microusd
    attempt = db.get(Attempt, uuid.UUID(attempt_id))
    assert attempt is not None
    db.refresh(attempt)
    assert attempt.evaluation_status == "evaluated" and attempt.evaluation_source == "ai"
    assert attempt.result["ai_feedback"]["observations"][0]["evidence"] == obs["evidence"]
    assert count(db, ReviewSchedule, ReviewSchedule.user_id == student.id) == 1
    detail = student.client.get(f"/api/v1/attempts/{attempt_id}").json()
    assert detail["result"]["ai_feedback"]["status"] == "evaluable"
    assert count(db, ProductEvent, ProductEvent.name == "feedback_viewed") == 1
    # La autoevaluación sigue posible después del feedback de IA.
    assessed = student.client.post(
        f"/api/v1/attempts/{attempt_id}/self-assessment",
        json={"scores": {"task": 2}},
        headers=student.headers(),
    )
    assert assessed.status_code == 200 and assessed.json()["result"]["ai_feedback"]
    assert len(evaluator.calls) == 1


def test_same_key_and_later_requests_never_charge_twice(
    student: Account, all_formats: dict[str, Any], db: Session, evaluator: FakeFeedbackEvaluator
) -> None:
    """AC-04: misma clave → mismo resultado y una ejecución; con otra clave tras un éxito se
    devuelve lo guardado; la clave con otro intento → 409."""
    attempt_id = write(student, all_formats)
    key = str(uuid.uuid4())
    first = ask(student, attempt_id, key).json()
    assert ask(student, attempt_id, key).json() == first
    assert ask(student, attempt_id).json() == first
    assert len(evaluator.calls) == 1
    assert count(db, AiRun, AiRun.user_id == student.id) == 1
    other = write(student, all_formats, TEXT.replace("Northside", "Riverside"))
    conflict = ask(student, other, key)
    assert (
        conflict.status_code == 409 and conflict.json()["error"]["code"] == "idempotency_conflict"
    )
    assert ask(student, attempt_id, "no-es-uuid").status_code == 422
    missing = student.client.post(
        f"/api/v1/attempts/{attempt_id}/feedback", headers=student.headers()
    )
    assert missing.status_code == 422


def test_unknown_keeps_the_reservation_and_is_never_retried(
    student: Account, all_formats: dict[str, Any], db: Session, evaluator: FakeFeedbackEvaluator
) -> None:
    """AC-04: un resultado desconocido conserva la reserva completa y no se repite."""
    attempt_id = write(student, all_formats, TEXT + " [[fake:unknown]]")
    body = ask(student, attempt_id).json()
    assert body["status"] == "unknown" and body["observations"] == []
    reserved, spent = user_budget(db, student.id)
    assert reserved > 0 and spent == 0
    assert ask(student, attempt_id).json()["status"] == "unknown"  # otra clave: no llama
    assert len(evaluator.calls) == 1
    attempt = db.get(Attempt, uuid.UUID(attempt_id))
    assert attempt is not None and attempt.evaluation_status == "pending"


def test_failed_releases_the_reservation_and_can_be_retried(
    student: Account, all_formats: dict[str, Any], db: Session, evaluator: FakeFeedbackEvaluator
) -> None:
    attempt_id = write(student, all_formats, TEXT + " [[fake:failed]]")
    body = ask(student, attempt_id).json()
    assert body["status"] == "failed"
    assert user_budget(db, student.id) == (0, 0)
    assert ask(student, attempt_id).json()["status"] == "failed"  # reintento permitido
    assert len(evaluator.calls) == 2


def test_not_evaluable_keeps_the_attempt_pending_without_review(
    student: Account, all_formats: dict[str, Any], db: Session
) -> None:
    attempt_id = write(student, all_formats, "Hi. Price please.")
    body = ask(student, attempt_id).json()
    assert body["status"] == "not_evaluable" and body["reason"] == "too_short"
    attempt = db.get(Attempt, uuid.UUID(attempt_id))
    assert attempt is not None and attempt.evaluation_status == "pending"
    assert count(db, ReviewSchedule, ReviewSchedule.user_id == student.id) == 0


def test_isolation_and_unsupported_formats(
    make_account: AccountFactory, all_formats: dict[str, Any]
) -> None:
    a, b = make_account("a@example.com"), make_account("b@example.com")
    attempt_id = write(a, all_formats)
    assert ask(b, attempt_id).status_code == 404
    assert ask(b, str(uuid.uuid4())).status_code == 404
    choice = all_formats["u1-l1-lectura"]["activities"]["u1.l1.p1"]
    closed = a.client.post(
        "/api/v1/attempts",
        json={"activity_id": choice, "response": {"selected": ["a"]}},
        headers={**a.headers(), "Idempotency-Key": str(uuid.uuid4())},
    ).json()["id"]
    res = ask(a, closed)
    assert res.status_code == 422 and res.json()["error"]["code"] == "feedback_not_supported"


def test_thumbs_on_an_observation_are_owned(
    make_account: AccountFactory, all_formats: dict[str, Any], db: Session
) -> None:
    a, b = make_account("a@example.com"), make_account("b@example.com")
    run_id = ask(a, write(a, all_formats)).json()["run_id"]

    def thumbs(acct: Account, rating: int, observation: int = 0) -> int:
        return acct.client.post(
            "/api/v1/feedback",
            json={
                "context_type": "ai_observation",
                "context_id": run_id,
                "rating": rating,
                "observation": observation,
            },
            headers=acct.headers(),
        ).status_code

    assert thumbs(a, 1) == 201 and thumbs(a, 0) == 201
    assert thumbs(b, 1) == 404  # feedback ajeno
    assert thumbs(a, 3) == 422  # solo 👍 (1) o 👎 (0)
    rows = db.scalars(select(UserFeedback).where(UserFeedback.context_type == "ai_observation"))
    assert sorted((r.rating, r.page) for r in rows) == [(0, "observation:0"), (1, "observation:0")]


def test_without_capability_or_budget_the_answer_is_an_expected_503(
    settings: Settings,
    uow: UnitOfWorkFactory,
    clock: FakeClock,
    make_account: AccountFactory,
    all_formats: dict[str, Any],
    container: Container,
    db: Session,
) -> None:
    """AC-02 (backend): sin presupuesto → `capability_disabled`; sin saldo →
    `budget_exhausted`; ninguno entra a `error_events` ni crea una ejecución."""
    from app.main import create_app
    from tests.conftest import TEST_ORIGIN
    from tests.helpers import login

    student = make_account("sinsaldo@example.com")
    attempt_id = write(student, all_formats)
    for update, code in (
        ({"feedback_provider": "fake"}, "capability_disabled"),
        ({**FUNDED, "budget_user_monthly_microusd": 1}, "budget_exhausted"),
    ):
        other = Container(
            settings=settings.model_copy(update=update),
            uow=uow,
            clock=clock,
            passwords=FAST_PASSWORDS,
            feedback_evaluator=FakeFeedbackEvaluator(),
            ready_providers=frozenset({"ai_feedback"}),
        )
        with TestClient(
            create_app(other.settings, container=other),
            base_url="https://testserver",
            headers={"Origin": TEST_ORIGIN},
        ) as c:
            csrf = login(c, student.email)
            res = c.post(
                f"/api/v1/attempts/{attempt_id}/feedback",
                headers={"X-CSRF-Token": csrf, "Idempotency-Key": str(uuid.uuid4())},
            )
        assert res.status_code == 503 and res.json()["error"]["code"] == code
    assert count(db, AiRun, AiRun.user_id == student.id) == 0
    assert count(db, ErrorEvent) == 0
