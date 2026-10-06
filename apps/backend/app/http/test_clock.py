"""`POST /api/test/clock` (solo `APP_ENV=test` con `TEST_CLOCK_ENABLED`): mueve el reloj de
la app para los E2E ("mañana" vencen los repasos). `create_app` solo la monta si el reloj de
prueba está activo, y `Settings` impide arrancar `prod` con `TEST_CLOCK_ENABLED`."""

from __future__ import annotations

from datetime import timedelta
from typing import Protocol

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.http.deps import ContainerDep

router = APIRouter(prefix="/api/test", tags=["test"], include_in_schema=False)


class MovableClock(Protocol):
    def advance(self, delta: timedelta) -> object: ...


class ClockIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    advance_hours: float = Field(default=0, ge=0, le=24 * 60)
    reset: bool = False


class ClockOut(BaseModel):
    now: str


@router.post("/clock", response_model=ClockOut)
def move_clock(body: ClockIn, container: ContainerDep) -> ClockOut:
    clock = container.clock
    if body.reset and hasattr(clock, "reset"):
        clock.reset()
    if body.advance_hours:
        mover: MovableClock = clock  # type: ignore[assignment]
        mover.advance(timedelta(hours=body.advance_hours))
    return ClockOut(now=clock.now().isoformat())
