"""Reglas puras de presupuesto (ADR-11, `docs/arquitectura.md` §9). Montos en micro-USD.

- Periodo: mes calendario en UTC (`YYYY-MM`).
- Reservar exige disponible = tope − reservado − gastado ≥ monto, en el presupuesto global
  y en el del alumno (fail-closed: sin tope configurado no hay capacidad).
- Conciliar pasa lo observado a gastado y libera el resto de la reserva; liberar devuelve la
  reserva completa (la llamada no ocurrió o falló sin costo). Un resultado desconocido
  conserva la reserva completa: nunca se supone consumo cero.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Literal

Capability = Literal["ai_feedback", "stt", "voice"]
Purpose = Literal["writing_feedback", "speaking_feedback", "transcription", "voice_session"]
RunStatus = Literal["reserved", "running", "succeeded", "failed", "unknown", "released"]

PURPOSES: tuple[Purpose, ...] = (
    "writing_feedback",
    "speaking_feedback",
    "transcription",
    "voice_session",
)
RUN_STATUSES: tuple[RunStatus, ...] = (
    "reserved",
    "running",
    "succeeded",
    "failed",
    "unknown",
    "released",
)
OPEN_STATUSES: frozenset[str] = frozenset({"reserved", "running"})
WARNING_RATIO = 0.8


class BudgetExceeded(Exception):
    """La reserva no cabe en el presupuesto `scope` (`global` o `user`)."""

    def __init__(self, scope: str) -> None:
        super().__init__(scope)
        self.scope = scope


def period_of(moment: datetime) -> str:
    return f"{moment.year:04d}-{moment.month:02d}"


@dataclass(frozen=True)
class Budget:
    limit: int
    reserved: int = 0
    spent: int = 0

    @property
    def available(self) -> int:
        return self.limit - self.reserved - self.spent

    @property
    def committed(self) -> int:
        """Lo que ya no está disponible: gastado más reservado."""
        return self.reserved + self.spent

    @property
    def warning(self) -> bool:
        return self.limit > 0 and self.committed >= WARNING_RATIO * self.limit


def reserve(budget: Budget, amount: int, scope: str) -> Budget:
    if amount < 0:
        raise ValueError("el monto de una reserva no puede ser negativo")
    if amount > budget.available:
        raise BudgetExceeded(scope)
    return replace(budget, reserved=budget.reserved + amount)


def settle(budget: Budget, reserved_amount: int, cost: int) -> Budget:
    """Pasa a gastado el costo observado y libera la reserva de esa ejecución."""
    if cost < 0:
        raise ValueError("el costo no puede ser negativo")
    return replace(
        budget,
        reserved=max(0, budget.reserved - reserved_amount),
        spent=budget.spent + cost,
    )


def release(budget: Budget, reserved_amount: int) -> Budget:
    return settle(budget, reserved_amount, 0)


def cost_for_tokens(
    input_tokens: int, output_tokens: int, input_per_mtok: int, output_per_mtok: int
) -> int:
    """Costo en micro-USD de una llamada por tokens, redondeado hacia arriba."""
    total = input_tokens * input_per_mtok + output_tokens * output_per_mtok
    return math.ceil(total / 1_000_000)


def cost_for_seconds(seconds: float, price_per_min: int) -> int:
    """Costo en micro-USD por segundos facturables (enteros, hacia arriba)."""
    billable = math.ceil(max(0.0, seconds))
    return math.ceil(billable * price_per_min / 60)


@dataclass(frozen=True)
class CapabilityState:
    capability: Capability
    enabled: bool
    reason: str | None = None  # flag_off · budget_missing · price_missing · provider_missing


def capability_state(
    capability: Capability,
    *,
    flag_on: bool,
    budgets_configured: bool,
    prices_configured: bool,
    provider_configured: bool,
) -> CapabilityState:
    """Fail-closed: cualquier pieza faltante deja la capacidad apagada, con su motivo."""
    for ok, reason in (
        (flag_on, "flag_off"),
        (budgets_configured, "budget_missing"),
        (prices_configured, "price_missing"),
        (provider_configured, "provider_missing"),
    ):
        if not ok:
            return CapabilityState(capability, enabled=False, reason=reason)
    return CapabilityState(capability, enabled=True)
