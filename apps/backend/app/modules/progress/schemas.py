"""DTO de progreso y repasos del alumno (listas permitidas)."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel


class RatioOut(BaseModel):
    """Numerador y denominador; con `total = 0` la interfaz dice "aún sin medición"."""

    correct: int
    total: int


class UnitAdvanceOut(RatioOut):
    unit: str
    title: str


class AdvanceOut(RatioOut):
    units: list[UnitAdvanceOut]


class ProductionStatOut(BaseModel):
    average: float | None
    count: int
    label: Literal["autoevaluación"]


class ProductionOut(BaseModel):
    writing: ProductionStatOut
    speaking: ProductionStatOut


class ReinforceOut(BaseModel):
    objective: str
    failed_at: str
    attempt_id: uuid.UUID
    item_id: uuid.UUID
    activity_key: str


class NextActionOut(BaseModel):
    kind: Literal["lesson", "scenario", "review", "done"]
    item_id: uuid.UUID | None = None
    title: str | None = None
    reason: Literal["in_progress", "next"] | None = None
    objective: str | None = None


class AidCountsOut(BaseModel):
    hint: int
    support_es: int
    transcript: int
    example: int


class ProgressOut(BaseModel):
    period_days: int
    advance: AdvanceOut
    initial_accuracy: RatioOut
    delayed_recall: RatioOut
    aids: AidCountsOut
    production: ProductionOut
    to_reinforce: list[ReinforceOut]
    streak_days: int
    reviews_due: int
    next_action: NextActionOut
    diagnostic_form_id: uuid.UUID | None


class ScheduleOut(BaseModel):
    objective: str
    stage: int
    due_at: str
    due: bool
    last_outcome: str


class ReviewsOut(BaseModel):
    due: list[ScheduleOut]
    upcoming: list[ScheduleOut]
