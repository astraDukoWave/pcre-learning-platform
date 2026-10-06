"""Orquestación pura del evaluador: prompt versionado → evaluador → validación.

La reserva de presupuesto, el guardado en el intento y los estados viven en el flujo de
REQ-02 (`practice`/`coaching`, CS-03); aquí solo se arma la llamada y se valida la salida.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.coaching.feedback import domain, prompts
from app.modules.coaching.feedback.ports import EvaluatorReply, FeedbackEvaluator, FeedbackRequest

# Cota de tokens de entrada para reservar: un token nunca tiene menos de un byte UTF-8 (los
# tokenizadores caen a bytes con lo que no conocen), más el esquema de salida que también viaja.
SCHEMA_TOKENS = 1024


@dataclass(frozen=True)
class Evaluation:
    feedback: domain.ValidatedFeedback
    reply: EvaluatorReply
    prompt_version: str


def max_tokens(prompt: str, evaluator: FeedbackEvaluator) -> tuple[int, int]:
    """Tokens máximos (entrada, salida) para la reserva antes de llamar."""
    return len(prompt.encode("utf-8")) + SCHEMA_TOKENS, evaluator.max_output_tokens


def evaluate(evaluator: FeedbackEvaluator, request: FeedbackRequest) -> Evaluation:
    """Llama al evaluador y valida. Deja pasar `EvaluatorFailed` y `EvaluatorUnknown`."""
    prompt = prompts.render(request)
    reply = evaluator.evaluate(prompt, request)
    feedback = domain.validate(
        reply.raw_text,
        learner_text=request.learner_text,
        criteria=frozenset(c.id for c in request.criteria),
        max_observations=domain.observation_cap(request.kind, request.max_observations),
    )
    return Evaluation(feedback=feedback, reply=reply, prompt_version=request.prompt_version)
