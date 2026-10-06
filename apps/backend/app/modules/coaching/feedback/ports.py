"""Puerto del evaluador de feedback (ADR-09). El texto del alumno viaja como dato."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

Kind = Literal["writing", "interview", "voice"]


@dataclass(frozen=True)
class Criterion:
    id: str
    name_es: str
    descriptors_es: tuple[str, ...]  # niveles 0 a 3


@dataclass(frozen=True)
class FeedbackRequest:
    kind: Kind
    prompt_version: str
    rubric_id: str
    rubric_version: int
    criteria: tuple[Criterion, ...]
    objective_es: str
    task_en: str
    learner_text: str
    max_observations: int


@dataclass(frozen=True)
class EvaluatorReply:
    raw_text: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


class EvaluatorFailed(Exception):
    """El proveedor respondió con un error o no se pudo enviar: sin costo, se puede reintentar."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class EvaluatorUnknown(Exception):
    """Se envió y no hubo respuesta (timeout, conexión cortada): resultado desconocido."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class FeedbackEvaluator(Protocol):
    provider: str
    model: str
    max_output_tokens: int

    def evaluate(self, prompt: str, request: FeedbackRequest) -> EvaluatorReply: ...
