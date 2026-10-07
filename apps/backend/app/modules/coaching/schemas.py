"""DTO de `coaching`. El feedback de IA y la transcripción solo existen después de enviar."""

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


class TranscribedWordOut(BaseModel):
    word: str
    confidence: float


class RepeatComparisonOut(BaseModel):
    recognized: int
    total: int
    recognized_ratio: float
    missing: list[str]


class TranscriptionOut(BaseModel):
    run_id: uuid.UUID
    attempt_id: uuid.UUID
    status: Literal["transcribed", "failed", "unknown"]
    reason: str | None
    kind: Literal["repeat", "interview"] | None
    text: str | None
    words: list[TranscribedWordOut]
    repeat: RepeatComparisonOut | None
    hint_es: str | None = None
    confirmed: bool | None
    disputed: bool | None
