"""DTO de `insights`: feedback del alumno y panel del piloto (admin)."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FeedbackIn(BaseModel):
    """Valoración de una lección o escenario (1–5, comentario opcional) o comentario
    general con la página como contexto (REQ-15)."""

    model_config = ConfigDict(extra="forbid")

    context_type: Literal["lesson", "general", "ai_observation"]
    context_id: uuid.UUID | None = None
    rating: int | None = Field(default=None, ge=0, le=5)
    message: str = Field(default="", max_length=1000)
    page: str | None = Field(default=None, max_length=200)
    # 👍/👎 de una observación del feedback con IA (MVP-02 REQ-02): su posición (0–2).
    observation: int | None = Field(default=None, ge=0, le=2)

    @model_validator(mode="after")
    def _check(self) -> FeedbackIn:
        if self.context_type == "lesson" and (self.context_id is None or not self.rating):
            raise ValueError("una valoración de lección lleva la lección y una nota de 1 a 5")
        if self.context_type == "ai_observation" and (
            self.context_id is None or self.rating not in (0, 1) or self.observation is None
        ):
            raise ValueError("👍/👎 lleva la ejecución, la observación y 1 (útil) o 0 (no útil)")
        if self.context_type == "general" and not self.message.strip():
            raise ValueError("escribe tu comentario")
        return self


class CreatedOut(BaseModel):
    id: uuid.UUID


class ActiveDayOut(BaseModel):
    day: str
    students: int


class FeedbackRowOut(BaseModel):
    id: uuid.UUID
    email: str
    context_type: str
    context_id: uuid.UUID | None
    rating: int | None
    message: str
    page: str | None
    created_at: str
    internal: bool | None = None


class ErrorRowOut(BaseModel):
    request_id: str
    route: str
    status_code: int
    error_code: str
    exception_type: str | None
    occurred_at: str


class PilotSummaryOut(BaseModel):
    days: int
    internal_excluded: bool
    active_by_day: list[ActiveDayOut]
    attempts: int
    lessons_completed: int
    reviews_done: int
    reviews_due: int
    diagnostics: int
    checkpoints: int
    average_rating: float | None
    ratings: int
    latest_comments: list[FeedbackRowOut]
    open_reports: int
    server_errors: int
    latest_errors: list[ErrorRowOut]


class LessonRatingOut(BaseModel):
    item_id: uuid.UUID
    title: str
    average: float
    count: int


class FeedbackOverviewOut(BaseModel):
    by_lesson: list[LessonRatingOut]
    latest: list[FeedbackRowOut]
