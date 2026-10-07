"""Casos de uso de `usage` (ADR-11): capacidades, reservas, conciliación y consumo.

Cada operación abre su propia transacción y la confirma antes de volver: la reserva debe
verse en otras peticiones antes de llamar al proveedor, y el resultado se concilia después,
fuera de la llamada. El orden de bloqueo es siempre global → alumno (sin deadlocks).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import ServiceUnavailable
from app.db.uow import UnitOfWorkFactory
from app.modules.usage import domain, repository
from app.modules.usage.domain import Budget, Capability, CapabilityState, Purpose
from app.modules.usage.models import AiRun

logger = logging.getLogger("app.usage")

UNAVAILABLE_MESSAGE = "Esta práctica no está disponible ahora. Puedes hacerla por texto."
CAPABILITY_FLAGS: dict[Capability, str] = {
    "ai_feedback": "ai_feedback_enabled",
    "stt": "stt_enabled",
    "voice": "voice_enabled",
}


class CapabilityDisabled(ServiceUnavailable):
    code = "capability_disabled"
    default_message = UNAVAILABLE_MESSAGE
    expected = True


class BudgetExhausted(ServiceUnavailable):
    code = "budget_exhausted"
    default_message = UNAVAILABLE_MESSAGE
    expected = True


@dataclass(frozen=True)
class RunView:
    id: uuid.UUID
    user_id: uuid.UUID
    purpose: str
    status: str
    attempt_id: uuid.UUID | None
    output: dict[str, Any] | None
    error_code: str | None
    voice_session_id: uuid.UUID | None = None


def _view(run: AiRun) -> RunView:
    return RunView(
        id=run.id,
        user_id=run.user_id,
        purpose=run.purpose,
        status=run.status,
        attempt_id=run.attempt_id,
        output=run.output,
        error_code=run.error_code,
        voice_session_id=run.voice_session_id,
    )


@dataclass(frozen=True)
class Reservation:
    run_id: uuid.UUID
    amount: int
    existing: bool  # la misma Idempotency-Key ya tenía una ejecución


def _prices_ok(settings: Settings, capability: Capability) -> bool:
    if capability == "ai_feedback":
        return (
            settings.gemini_price_input_per_mtok_microusd is not None
            and settings.gemini_price_output_per_mtok_microusd is not None
        )
    return True  # STT y voz tienen precio por defecto (pricing del 5 oct 2026)


def _budgets_ok(settings: Settings, capability: Capability) -> bool:
    budgets = (
        settings.budget_global_monthly_microusd is not None
        and settings.budget_user_monthly_microusd is not None
    )
    if capability == "voice":
        return budgets and settings.voice_max_minutes_per_user_month is not None
    return budgets


class UsageService:
    def __init__(
        self,
        uow: UnitOfWorkFactory,
        clock: Clock,
        settings: Settings,
        provider_ready: Callable[[Capability], bool] = lambda _: False,
    ) -> None:
        self.uow = uow
        self.clock = clock
        self.settings = settings
        self.provider_ready = provider_ready

    # -- capacidades --------------------------------------------------------------------

    def capability(self, capability: Capability) -> CapabilityState:
        return domain.capability_state(
            capability,
            flag_on=bool(getattr(self.settings, CAPABILITY_FLAGS[capability])),
            budgets_configured=_budgets_ok(self.settings, capability),
            prices_configured=_prices_ok(self.settings, capability),
            provider_configured=self.provider_ready(capability),
        )

    def capabilities(self) -> dict[Capability, CapabilityState]:
        return {c: self.capability(c) for c in CAPABILITY_FLAGS}

    def enabled_capabilities(self) -> dict[Capability, bool]:
        """Para la interfaz del alumno: solo si cada capacidad está encendida."""
        return {c: state.enabled for c, state in self.capabilities().items()}

    def require(self, capability: Capability) -> None:
        state = self.capability(capability)
        if not state.enabled:
            logger.info(
                "capability_disabled", extra={"capability": capability, "reason": state.reason}
            )
            raise CapabilityDisabled()

    # -- reservas -----------------------------------------------------------------------

    def reserve(
        self,
        user_id: uuid.UUID,
        *,
        purpose: Purpose,
        amount: int,
        idempotency_key: str,
        provider: str,
        model: str | None = None,
        prompt_version: str | None = None,
        rubric_version: str | None = None,
        attempt_id: uuid.UUID | None = None,
        voice_session_id: uuid.UUID | None = None,
        voice_seconds: int | None = None,
        one_per_target: tuple[str, ...] | None = None,
    ) -> Reservation:
        """Reserva `amount` micro-USD en el presupuesto global y en el del alumno y crea la
        ejecución `reserved`. Con la misma clave devuelve la ejecución existente. Para voz,
        `voice_seconds` es el máximo de la sesión y cuenta contra los minutos del alumno.
        Con `one_per_target` (propósitos), si el intento o la sesión de voz ya tienen una
        ejecución que no falló, la devuelve en vez de crear otra: dos peticiones con claves
        distintas a la vez nunca pagan dos llamadas (REQ-02: solo se reintenta tras `failed`)."""
        if self.settings.budget_global_monthly_microusd is None or (
            self.settings.budget_user_monthly_microusd is None
        ):
            raise CapabilityDisabled()
        now = self.clock.now()
        period = domain.period_of(now)
        with self.uow() as s:
            # El bloqueo global serializa las reservas: la búsqueda por clave va después, así
            # dos peticiones con la misma clave nunca crean dos ejecuciones.
            global_row = repository.lock_budget(
                s,
                scope="global",
                period=period,
                limit=self.settings.budget_global_monthly_microusd,
                now=now,
            )
            existing = repository.run_by_key(s, user_id, purpose, idempotency_key)
            if existing is not None:
                return Reservation(existing.id, existing.reserved_microusd, existing=True)
            if one_per_target and (attempt_id is not None or voice_session_id is not None):
                live = repository.live_run_for_target(
                    s,
                    user_id,
                    one_per_target,
                    attempt_id=attempt_id,
                    voice_session_id=voice_session_id,
                )
                if live is not None:
                    return Reservation(live.id, live.reserved_microusd, existing=True)
            user_row = repository.lock_budget(
                s,
                scope="user",
                period=period,
                limit=self.settings.budget_user_monthly_microusd,
                now=now,
                user_id=user_id,
            )
            try:
                if voice_seconds is not None:
                    self._check_voice_minutes(s, user_id, period, voice_seconds)
                g = domain.reserve(_budget(global_row), amount, "global")
                u = domain.reserve(_budget(user_row), amount, "user")
            except domain.BudgetExceeded as exc:
                logger.info("budget_exhausted", extra={"scope": exc.scope, "purpose": purpose})
                raise BudgetExhausted() from exc
            global_row.reserved_microusd, user_row.reserved_microusd = g.reserved, u.reserved
            global_row.updated_at = user_row.updated_at = now
            run = AiRun(
                id=uuid.uuid4(),
                user_id=user_id,
                purpose=purpose,
                period=period,
                provider=provider,
                model=model,
                prompt_version=prompt_version,
                rubric_version=rubric_version,
                attempt_id=attempt_id,
                voice_session_id=voice_session_id,
                status="reserved",
                reserved_microusd=amount,
                # Voz: mientras la sesión está abierta, las unidades son los segundos
                # reservados; al conciliar pasan a ser los facturables observados.
                observed_units=voice_seconds,
                idempotency_key=idempotency_key,
                created_at=now,
            )
            repository.add_run(s, run)
        return Reservation(run.id, amount, existing=False)

    def _check_voice_minutes(self, s: Any, user_id: uuid.UUID, period: str, seconds: int) -> None:
        cap = self.settings.voice_max_minutes_per_user_month
        if cap is None:
            raise CapabilityDisabled()
        if repository.voice_seconds(s, user_id, period) + seconds > cap * 60:
            raise domain.BudgetExceeded("voice_minutes")

    def mark_running(self, run_id: uuid.UUID) -> None:
        with self.uow() as s:
            run = repository.run_for_update(s, run_id)
            if run is not None and run.status == "reserved":
                run.status = "running"

    def settle(
        self,
        run_id: uuid.UUID,
        *,
        cost: int,
        observed_units: int | None,
        output: dict[str, Any] | None = None,
        latency_ms: int | None = None,
        status: str = "succeeded",
        error_code: str | None = None,
    ) -> None:
        """Concilia: gastado += costo observado; se libera el resto de la reserva."""
        self._close(run_id, status, cost, observed_units, output, latency_ms, error_code)

    def release(self, run_id: uuid.UUID, *, error_code: str, latency_ms: int | None = None) -> None:
        """La llamada falló sin costo (no se envió, o el proveedor respondió un error):
        `failed` y la reserva vuelve al disponible."""
        self._close(run_id, "failed", 0, 0, None, latency_ms, error_code)

    def mark_unknown(self, run_id: uuid.UUID, *, error_code: str) -> None:
        """Resultado desconocido (timeout tras enviar, caída): la reserva completa queda
        comprometida y nunca se reintenta sola."""
        now = self.clock.now()
        with self.uow() as s:
            run = repository.run_for_update(s, run_id)
            if run is None or run.status not in domain.OPEN_STATUSES:
                return
            run.status = "unknown"
            run.error_code = error_code
            run.finished_at = now
        logger.warning("ai_run_unknown", extra={"purpose": run.purpose, "error_code": error_code})

    def stale_open_runs(
        self, purpose: str, *, created_before: datetime
    ) -> list[tuple[uuid.UUID, uuid.UUID | None]]:
        """Ejecuciones `reserved` o `running` de `purpose` creadas antes de `created_before`:
        `(id, voice_session_id)`, para que su dueño las concilie."""
        with self.uow() as s:
            return [
                (run.id, run.voice_session_id)
                for run in repository.open_runs(s, purpose, created_before)
            ]

    def attach_voice_session(self, run_id: uuid.UUID, voice_session_id: uuid.UUID) -> None:
        """La reserva de voz se hace antes de crear la sesión; aquí se enlazan."""
        with self.uow() as s:
            run = repository.run_for_update(s, run_id)
            if run is not None:
                run.voice_session_id = voice_session_id

    def expire_as_spent(self, run_id: uuid.UUID, *, error_code: str) -> None:
        """Una ejecución abandonada (sesión huérfana): la reserva completa pasa a gastado."""
        with self.uow() as s:
            run = repository.run_for_update(s, run_id)
            if run is None:
                return
            amount = run.reserved_microusd
        self._close(run_id, "unknown", amount, None, None, None, error_code)

    def _close(
        self,
        run_id: uuid.UUID,
        status: str,
        cost: int,
        observed_units: int | None,
        output: dict[str, Any] | None,
        latency_ms: int | None,
        error_code: str | None,
    ) -> None:
        now = self.clock.now()
        with self.uow() as s:
            run = repository.run_for_update(s, run_id)
            if run is None or run.status not in domain.OPEN_STATUSES:
                return  # ya conciliada: idempotente
            limits = self.settings
            global_row = repository.lock_budget(
                s,
                scope="global",
                period=run.period,
                limit=limits.budget_global_monthly_microusd or 0,
                now=now,
            )
            user_row = repository.lock_budget(
                s,
                scope="user",
                period=run.period,
                limit=limits.budget_user_monthly_microusd or 0,
                now=now,
                user_id=run.user_id,
            )
            for row in (global_row, user_row):
                settled = domain.settle(_budget(row), run.reserved_microusd, cost)
                row.reserved_microusd, row.spent_microusd = settled.reserved, settled.spent
                row.updated_at = now
            run.status = status
            run.cost_microusd = cost
            if observed_units is not None or status != "unknown":
                run.observed_units = observed_units
            run.output = output
            run.latency_ms = latency_ms
            run.error_code = error_code
            run.finished_at = now
            purpose, model = run.purpose, run.model
        logger.info(
            "ai_run_finished",
            extra={
                "purpose": purpose,
                "model": model,
                "run_status": status,
                "latency_ms": latency_ms,
                "cost_microusd": cost,
            },
        )

    # -- consulta de ejecuciones ---------------------------------------------------------

    def run_view(self, run_id: uuid.UUID) -> RunView | None:
        with self.uow() as s:
            run = repository.run(s, run_id)
            return _view(run) if run is not None else None

    def run_by_key(self, user_id: uuid.UUID, purpose: str, key: str) -> RunView | None:
        with self.uow() as s:
            run = repository.run_by_key(s, user_id, purpose, key)
            return _view(run) if run is not None else None

    def latest_for_attempt(
        self, user_id: uuid.UUID, attempt_id: uuid.UUID, purposes: tuple[str, ...]
    ) -> RunView | None:
        with self.uow() as s:
            run = repository.latest_run_for_attempt(s, user_id, attempt_id, purposes)
            return _view(run) if run is not None else None

    def latest_for_voice_session(
        self, user_id: uuid.UUID, voice_session_id: uuid.UUID, purpose: str
    ) -> RunView | None:
        with self.uow() as s:
            run = repository.latest_run_for_voice_session(s, user_id, voice_session_id, purpose)
            return _view(run) if run is not None else None

    # -- admin --------------------------------------------------------------------------

    def overview(self, period: str | None = None) -> dict[str, Any]:
        period = period or domain.period_of(self.clock.now())
        with self.uow() as s:
            g = repository.budget(s, scope="global", period=period)
            users = repository.usage_by_user(s, period)
            purposes = repository.runs_by_purpose(s, period)
        limit = self.settings.budget_global_monthly_microusd
        budget = Budget(
            limit=limit if limit is not None else (g.limit_microusd if g else 0),
            reserved=g.reserved_microusd if g else 0,
            spent=g.spent_microusd if g else 0,
        )
        return {
            "period": period,
            "period_note": "Mes calendario en UTC.",
            "capabilities": [
                {"capability": c.capability, "enabled": c.enabled, "reason": c.reason}
                for c in self.capabilities().values()
            ],
            "global_budget": {
                "configured": limit is not None,
                "limit_microusd": budget.limit,
                "reserved_microusd": budget.reserved,
                "spent_microusd": budget.spent,
                "estimated_microusd": budget.committed,
                "warning": budget.warning,
            },
            "user_limit_microusd": self.settings.budget_user_monthly_microusd,
            "voice_minutes_per_user": self.settings.voice_max_minutes_per_user_month,
            "calls_by_purpose": purposes,
            "users": [
                {**u, "estimated_microusd": u["reserved_microusd"] + u["spent_microusd"]}
                for u in users
            ],
        }


def _budget(row: Any) -> Budget:
    return Budget(
        limit=int(row.limit_microusd),
        reserved=int(row.reserved_microusd),
        spent=int(row.spent_microusd),
    )
