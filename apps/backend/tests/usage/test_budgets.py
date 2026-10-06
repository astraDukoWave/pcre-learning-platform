"""REQ-01 y ADR-11: dominio del presupuesto, servicio fail-closed, conciliación, minutos de
voz, vista del admin y AC-01 (dos reservas concurrentes que juntas exceden el tope → una
sola tiene éxito, con dos hilos contra PostgreSQL real)."""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.bootstrap import Container
from app.core.clock import FakeClock
from app.core.config import Settings
from app.db.uow import UnitOfWorkFactory
from app.modules.insights.models import ErrorEvent
from app.modules.usage import domain
from app.modules.usage.models import AiRun, BudgetPeriod
from app.modules.usage.service import BudgetExhausted, CapabilityDisabled, UsageService
from tests.conftest import FAST_PASSWORDS
from tests.helpers import Account, create_user

FUNDED = {
    "ai_feedback_enabled": True,
    "stt_enabled": True,
    "voice_enabled": True,
    "budget_global_monthly_microusd": 1_000_000,  # USD 1
    "budget_user_monthly_microusd": 400_000,
    "voice_max_minutes_per_user_month": 11,
    "gemini_price_input_per_mtok_microusd": 100_000,
    "gemini_price_output_per_mtok_microusd": 400_000,
}
ALL_PROVIDERS = frozenset({"ai_feedback", "stt", "voice"})


@pytest.fixture
def container(settings: Settings, uow: UnitOfWorkFactory, clock: FakeClock) -> Container:
    return Container(
        settings=settings.model_copy(update=FUNDED),
        uow=uow,
        clock=clock,
        passwords=FAST_PASSWORDS,
        ready_providers=ALL_PROVIDERS,
    )


@pytest.fixture
def usage(container: Container) -> UsageService:
    return UsageService(
        container.uow, container.clock, container.settings, container.provider_ready
    )


def reserve(svc: UsageService, user_id: uuid.UUID, amount: int, **kw: Any) -> domain.Purpose:
    kw.setdefault("purpose", "writing_feedback")
    kw.setdefault("idempotency_key", str(uuid.uuid4()))
    return svc.reserve(user_id, amount=amount, provider="fake", **kw)  # type: ignore[return-value]


# -- dominio --------------------------------------------------------------------------


def test_domain_reserve_settle_release_and_costs() -> None:
    b = domain.Budget(limit=100)
    b = domain.reserve(b, 60, "global")
    assert (b.reserved, b.available) == (60, 40)
    with pytest.raises(domain.BudgetExceeded) as err:
        domain.reserve(b, 41, "global")
    assert err.value.scope == "global"
    b = domain.settle(b, 60, 25)  # gastó 25 de los 60 reservados
    assert (b.reserved, b.spent, b.available) == (0, 25, 75)
    assert domain.release(domain.Budget(100, reserved=30), 30).available == 100
    assert domain.Budget(100, reserved=50, spent=30).warning is True
    assert domain.Budget(100, reserved=50, spent=29).warning is False
    assert domain.period_of(datetime(2026, 12, 31, 23, 59, tzinfo=UTC)) == "2026-12"
    # 1 000 tokens de entrada a USD 0.10/M y 500 de salida a USD 0.40/M → 300 micro-USD.
    assert domain.cost_for_tokens(1000, 500, 100_000, 400_000) == 300
    assert domain.cost_for_seconds(61.2, 75_000) == 77_500  # 62 s facturables
    assert domain.cost_for_seconds(0, 75_000) == 0


def test_domain_capability_is_fail_closed() -> None:
    ok = domain.capability_state(
        "voice",
        flag_on=True,
        budgets_configured=True,
        prices_configured=True,
        provider_configured=True,
    )
    assert ok.enabled and ok.reason is None
    for missing, reason in (
        ("flag_on", "flag_off"),
        ("budgets_configured", "budget_missing"),
        ("prices_configured", "price_missing"),
        ("provider_configured", "provider_missing"),
    ):
        flags = {
            "flag_on": True,
            "budgets_configured": True,
            "prices_configured": True,
            "provider_configured": True,
            missing: False,
        }
        state = domain.capability_state("ai_feedback", **flags)
        assert not state.enabled and state.reason == reason


# -- servicio -------------------------------------------------------------------------


def test_without_budget_every_capability_is_disabled(
    settings: Settings, uow: UnitOfWorkFactory, clock: FakeClock, db: Session, container: Container
) -> None:
    flags_only = settings.model_copy(
        update={"ai_feedback_enabled": True, "stt_enabled": True, "voice_enabled": True}
    )
    svc = UsageService(uow, clock, flags_only, lambda _: True)
    states = svc.capabilities()
    assert {c: s.reason for c, s in states.items()} == {
        "ai_feedback": "budget_missing",
        "stt": "budget_missing",
        "voice": "budget_missing",
    }
    with pytest.raises(CapabilityDisabled):
        svc.require("ai_feedback")
    user = create_user(db, container, "sinpresupuesto@example.com")
    with pytest.raises(CapabilityDisabled):
        svc.reserve(
            user.id, purpose="transcription", amount=1, idempotency_key="k", provider="fake"
        )
    default = UsageService(uow, clock, settings)  # configuración de MVP-01: todo apagado
    assert all(s.reason == "flag_off" for s in default.capabilities().values())


def test_reserve_settle_and_release_move_the_budgets(
    usage: UsageService, db: Session, container: Container
) -> None:
    user = create_user(db, container, "consumo@example.com")
    r = usage.reserve(
        user.id, purpose="writing_feedback", amount=3000, idempotency_key="k1", provider="fake"
    )
    again = usage.reserve(
        user.id, purpose="writing_feedback", amount=3000, idempotency_key="k1", provider="fake"
    )
    assert again.run_id == r.run_id and again.existing and not r.existing
    period = domain.period_of(container.clock.now())
    user_row = db.scalars(select(BudgetPeriod).where(BudgetPeriod.user_id == user.id)).one()
    assert (user_row.reserved_microusd, user_row.spent_microusd) == (3000, 0)

    usage.settle(r.run_id, cost=1200, observed_units=900, output={"status": "evaluable"})
    usage.settle(r.run_id, cost=9999, observed_units=1)  # ya conciliada: no cambia nada
    db.expire_all()
    rows = {
        b.scope: b for b in db.scalars(select(BudgetPeriod).where(BudgetPeriod.period == period))
    }
    assert (rows["user"].reserved_microusd, rows["user"].spent_microusd) == (0, 1200)
    assert (rows["global"].reserved_microusd, rows["global"].spent_microusd) == (0, 1200)
    run = db.get(AiRun, r.run_id)
    assert run is not None and run.status == "succeeded" and run.cost_microusd == 1200

    failed = usage.reserve(
        user.id, purpose="transcription", amount=500, idempotency_key="k2", provider="fake"
    )
    usage.release(failed.run_id, error_code="provider_error")
    db.expire_all()
    assert db.get(AiRun, failed.run_id).status == "failed"  # type: ignore[union-attr]
    user_row = db.scalars(select(BudgetPeriod).where(BudgetPeriod.user_id == user.id)).one()
    assert (user_row.reserved_microusd, user_row.spent_microusd) == (0, 1200)


def test_unknown_keeps_the_full_reservation(
    usage: UsageService, db: Session, container: Container
) -> None:
    user = create_user(db, container, "desconocido@example.com")
    r = usage.reserve(
        user.id, purpose="writing_feedback", amount=250_000, idempotency_key="k", provider="fake"
    )
    usage.mark_unknown(r.run_id, error_code="timeout")
    usage.settle(r.run_id, cost=1, observed_units=1)  # un desconocido no se concilia solo
    db.expire_all()
    user_row = db.scalars(select(BudgetPeriod).where(BudgetPeriod.user_id == user.id)).one()
    assert user_row.reserved_microusd == 250_000  # nunca se supone consumo cero
    assert db.get(AiRun, r.run_id).status == "unknown"  # type: ignore[union-attr]
    with pytest.raises(BudgetExhausted):  # 400 000 de tope por alumno: no caben 200 000 más
        usage.reserve(
            user.id,
            purpose="writing_feedback",
            amount=200_000,
            idempotency_key="k3",
            provider="fake",
        )
    usage.expire_as_spent(r.run_id, error_code="orphan")  # ya no está abierta: sin cambios
    db.expire_all()
    assert (
        db.scalars(select(BudgetPeriod).where(BudgetPeriod.user_id == user.id)).one().spent_microusd
        == 0
    )


def test_user_and_global_limits_and_voice_minutes(
    usage: UsageService, db: Session, container: Container
) -> None:
    a = create_user(db, container, "a@example.com")
    b = create_user(db, container, "b@example.com")
    c = create_user(db, container, "c@example.com")
    usage.reserve(
        a.id, purpose="writing_feedback", amount=400_000, idempotency_key="1", provider="fake"
    )
    with pytest.raises(BudgetExhausted):  # tope por alumno
        usage.reserve(
            a.id, purpose="writing_feedback", amount=1, idempotency_key="2", provider="fake"
        )
    usage.reserve(
        b.id, purpose="writing_feedback", amount=400_000, idempotency_key="1", provider="fake"
    )
    with pytest.raises(BudgetExhausted):  # tope global (1 000 000): quedan 200 000
        usage.reserve(
            c.id, purpose="writing_feedback", amount=200_001, idempotency_key="1", provider="fake"
        )
    # Voz: 11 minutos (660 s) por alumno al mes; cada sesión reserva 300 s.
    first = usage.reserve(
        c.id,
        purpose="voice_session",
        amount=1000,
        idempotency_key="v1",
        provider="fake",
        voice_seconds=300,
    )
    usage.reserve(
        c.id,
        purpose="voice_session",
        amount=1000,
        idempotency_key="v2",
        provider="fake",
        voice_seconds=300,
    )
    with pytest.raises(BudgetExhausted):
        usage.reserve(
            c.id,
            purpose="voice_session",
            amount=1000,
            idempotency_key="v3",
            provider="fake",
            voice_seconds=300,
        )
    usage.settle(first.run_id, cost=500, observed_units=60, status="succeeded")  # 60 + 300 + 300
    usage.reserve(
        c.id,
        purpose="voice_session",
        amount=1000,
        idempotency_key="v4",
        provider="fake",
        voice_seconds=300,
    )


def test_admin_usage_view_and_guard(
    usage: UsageService, admin: Account, student: Account, client: TestClient
) -> None:
    r = usage.reserve(
        student.id,
        purpose="writing_feedback",
        amount=400_000,
        idempotency_key="x",
        provider="fake",
    )
    usage.settle(r.run_id, cost=350_000, observed_units=1000)
    usage.reserve(
        admin.id, purpose="transcription", amount=400_000, idempotency_key="y", provider="fake"
    )
    assert student.client.get("/api/v1/admin/usage").status_code == 403
    assert client.get("/api/v1/admin/usage").status_code == 401
    body = admin.client.get("/api/v1/admin/usage").json()
    g = body["global_budget"]
    assert (g["limit_microusd"], g["spent_microusd"], g["reserved_microusd"]) == (
        1_000_000,
        350_000,
        400_000,
    )
    assert g["estimated_microusd"] == 750_000 and g["warning"] is False  # 75 % < 80 %
    assert body["period_note"] == "Mes calendario en UTC."
    rows = {u["email"]: u for u in body["users"]}
    assert rows["alumna@example.com"]["spent_microusd"] == 350_000
    assert rows["alumna@example.com"]["calls"] == 1
    assert body["calls_by_purpose"] == {"writing_feedback": 1, "transcription": 1}
    usage.reserve(
        student.id, purpose="transcription", amount=50_000, idempotency_key="z", provider="fake"
    )
    assert admin.client.get("/api/v1/admin/usage").json()["global_budget"]["warning"] is True
    bad = admin.client.get("/api/v1/admin/usage", params={"period": "2026-13"})
    assert bad.status_code == 422


def test_expected_503_is_not_a_server_error(
    settings: Settings, uow: UnitOfWorkFactory, clock: FakeClock, db: Session
) -> None:
    from app.main import create_app
    from tests.conftest import TEST_ORIGIN

    c = Container(settings=settings, uow=uow, clock=clock, passwords=FAST_PASSWORDS)
    app = create_app(settings, container=c)
    from fastapi import APIRouter

    probe = APIRouter()

    @probe.get("/api/v1/_probe")
    def _probe() -> None:
        UsageService(uow, clock, settings).require("voice")

    app.router.routes.insert(0, probe.routes[0])
    with TestClient(app, base_url="https://testserver", headers={"Origin": TEST_ORIGIN}) as tc:
        res = tc.get("/api/v1/_probe")
    assert res.status_code == 503 and res.json()["error"]["code"] == "capability_disabled"
    assert db.scalar(select(func.count()).select_from(ErrorEvent)) == 0


# -- AC-01 ----------------------------------------------------------------------------


def test_concurrent_reservations_over_the_limit_only_one_succeeds(
    committed_container: Container,
) -> None:
    c = committed_container
    settings = c.settings.model_copy(
        update={
            **FUNDED,
            "budget_global_monthly_microusd": 100,
            "budget_user_monthly_microusd": 100,
        }
    )
    with c.uow() as s:
        ids = [create_user(s, c, f"u{i}@race.example.com").id for i in range(2)]
    svc = UsageService(c.uow, c.clock, settings, lambda _: True)
    barrier = threading.Barrier(2)
    outcomes: list[str] = ["", ""]

    def worker(i: int) -> None:
        barrier.wait()
        try:
            svc.reserve(
                ids[i],
                purpose="writing_feedback",
                amount=60,
                idempotency_key="race",
                provider="fake",
            )
            outcomes[i] = "ok"
        except BudgetExhausted:
            outcomes[i] = "exhausted"

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(outcomes) == ["exhausted", "ok"]
    period = domain.period_of(c.clock.now())
    with c.uow() as s:
        g = s.scalars(
            select(BudgetPeriod).where(
                BudgetPeriod.scope == "global", BudgetPeriod.period == period
            )
        ).one()
        assert (g.reserved_microusd, g.spent_microusd) == (60, 0)
        assert s.scalar(select(func.count()).select_from(AiRun).where(AiRun.user_id.in_(ids))) == 1
