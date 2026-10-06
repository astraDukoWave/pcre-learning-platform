"""DTO de `coaching`. El feedback de IA solo existe después de enviar."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel


class AiObservationOut(BaseModel):
    criterion: str
    criterion_name_es: str
    evidence: str
    observation_es: str
    suggestion_es: str


class AiFeedbackOut(BaseModel):
    run_id: uuid.UUID
    attempt_id: uuid.UUID
    status: Literal["evaluable", "not_evaluable", "failed", "unknown"]
    reason: str | None
    label: str
    observations: list[AiObservationOut]
    rubric_levels: dict[str, int]
