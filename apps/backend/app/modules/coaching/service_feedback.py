"""Feedback abierto de escritura y de entrevista transcrita (MVP-02 REQ-02).

Flujo: capacidad encendida → intento propio que lo admite → ejecución previa (la misma clave
devuelve lo mismo; solo se reintenta tras `failed`; un `unknown` no se repite) → reserva del
costo máximo → evaluador (20 s) → validación con evidencia literal → conciliación → guardado
en el intento. Ninguna transacción queda abierta durante la llamada al proveedor.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.core.config import Settings
from app.core.errors import Conflict, NotFound
from app.modules.coaching.feedback import prompts
from app.modules.coaching.feedback import service as engine
from app.modules.coaching.feedback.ports import (
    Criterion,
    EvaluatorFailed,
    EvaluatorUnknown,
    FeedbackEvaluator,
    FeedbackRequest,
)
from app.modules.practice.service import FeedbackTarget, Learner, PracticeService
from app.modules.usage import domain as usage_domain
from app.modules.usage.service import CapabilityDisabled, RunView, UsageService

logger = logging.getLogger("app.coaching")

LABEL = "Feedback automático orientativo (IA)"
PURPOSES = ("writing_feedback", "speaking_feedback")
MAX_OBSERVATIONS = 3


def criteria_from(rubric: dict[str, Any] | None) -> tuple[Criterion, ...]:
    """Criterios que evalúa la IA: los de la rúbrica salvo los de solo autoevaluación."""
    out = []
    for c in (rubric or {}).get("criteria", []):
        if c.get("self_assessed_only"):
            continue
        levels = sorted(c.get("levels", []), key=lambda level: level.get("score", 0))
        out.append(
            Criterion(
                id=c["id"],
                name_es=c.get("name_es", c["id"]),
                descriptors_es=tuple(level.get("descriptor_es", "") for level in levels),
            )
        )
    return tuple(out)


class FeedbackFlowService:
    def __init__(
        self,
        settings: Settings,
        usage: UsageService,
        practice: PracticeService,
        evaluator: FeedbackEvaluator | None,
    ) -> None:
        self.settings = settings
        self.usage = usage
        self.practice = practice
        self.evaluator = evaluator

    def request_feedback(
        self, learner: Learner, attempt_id: uuid.UUID, idempotency_key: str
    ) -> dict[str, Any]:
        self.usage.require("ai_feedback")
        if self.evaluator is None:
            raise CapabilityDisabled()
        target = self.practice.feedback_target(learner, attempt_id)
        purpose = "writing_feedback" if target.kind == "writing" else "speaking_feedback"
        same_key = self.usage.run_by_key(learner.user_id, purpose, idempotency_key)
        if same_key is not None:
            if same_key.attempt_id != attempt_id:
                raise Conflict(
                    "Esta clave ya se usó con otra respuesta.", code="idempotency_conflict"
                )
            return self._from_run(same_key, target)
        latest = self.usage.latest_for_attempt(learner.user_id, attempt_id, PURPOSES)
        if latest is not None and latest.status != "failed":
            return self._from_run(latest, target)  # sin otra llamada ni otro cobro
        return self._evaluate(learner, target, purpose, idempotency_key)

    def _evaluate(
        self, learner: Learner, target: FeedbackTarget, purpose: str, key: str
    ) -> dict[str, Any]:
        evaluator = self.evaluator
        assert evaluator is not None
        criteria = criteria_from(target.rubric)
        rubric = target.rubric or {}
        request = FeedbackRequest(
            kind="writing" if target.kind == "writing" else "interview",
            prompt_version=prompts.VERSIONS["writing" if target.kind == "writing" else "interview"],
            rubric_id=str(rubric.get("id", "")),
            rubric_version=int(rubric.get("version", 1)),
            criteria=criteria,
            objective_es=target.objective_es,
            task_en=target.task_en,
            learner_text=target.learner_text,
            max_observations=MAX_OBSERVATIONS,
        )
        price_in = self.settings.gemini_price_input_per_mtok_microusd or 0
        price_out = self.settings.gemini_price_output_per_mtok_microusd or 0
        max_in, max_out = engine.max_tokens(prompts.render(request), evaluator)
        reservation = self.usage.reserve(
            learner.user_id,
            purpose=purpose,  # type: ignore[arg-type]
            amount=usage_domain.cost_for_tokens(max_in, max_out, price_in, price_out),
            idempotency_key=key,
            provider=evaluator.provider,
            model=evaluator.model,
            prompt_version=request.prompt_version,
            rubric_version=f"{request.rubric_id}-v{request.rubric_version}",
            attempt_id=target.attempt_id,
        )
        if reservation.existing:  # otra petición con la misma clave llegó primero
            view = self.usage.run_view(reservation.run_id)
            assert view is not None
            return self._from_run(view, target)
        run_id = reservation.run_id
        self.usage.mark_running(run_id)
        try:
            evaluation = engine.evaluate(evaluator, request)
        except EvaluatorFailed as exc:
            self.usage.release(run_id, error_code=exc.code)
            logger.warning("ai_feedback_failed", extra={"error_code": exc.code})
            return self._result(run_id, {"status": "failed", "reason": exc.code}, target)
        except EvaluatorUnknown as exc:
            self.usage.mark_unknown(run_id, error_code=exc.code)
            return self._result(run_id, {"status": "unknown", "reason": exc.code}, target)
        except Exception:
            # Un error propio después de llamar: no se supone consumo cero.
            self.usage.mark_unknown(run_id, error_code="internal_error")
            raise
        reply = evaluation.reply
        feedback = evaluation.feedback.as_dict()
        self.usage.settle(
            run_id,
            cost=usage_domain.cost_for_tokens(
                reply.input_tokens, reply.output_tokens, price_in, price_out
            ),
            observed_units=reply.input_tokens + reply.output_tokens,
            output=feedback,
            latency_ms=reply.latency_ms,
        )
        shown = self._result(run_id, feedback, target)
        # El intento guarda la misma vista que devuelve la API (etiqueta y nombres de
        # criterio), así lo guardado se ve igual al recargar.
        stored = {**shown, "run_id": str(run_id), "attempt_id": str(target.attempt_id)}
        self.practice.store_ai_feedback(
            learner, target.attempt_id, stored, run_id=run_id, objectives=target.objectives
        )
        return shown

    def _from_run(self, run: RunView, target: FeedbackTarget) -> dict[str, Any]:
        if run.status in ("reserved", "running"):
            raise Conflict("El feedback anterior sigue en curso.", code="feedback_in_progress")
        if run.status == "succeeded" and run.output is not None:
            return self._result(run.id, run.output, target)
        status = "unknown" if run.status == "unknown" else "failed"
        return self._result(run.id, {"status": status, "reason": run.error_code}, target)

    def _result(
        self, run_id: uuid.UUID, feedback: dict[str, Any], target: FeedbackTarget
    ) -> dict[str, Any]:
        names = {c.id: c.name_es for c in criteria_from(target.rubric)}
        return {
            "run_id": run_id,
            "attempt_id": target.attempt_id,
            "status": feedback.get("status"),
            "reason": feedback.get("reason"),
            "label": LABEL,
            "observations": [
                {**o, "criterion_name_es": names.get(o.get("criterion", ""), o.get("criterion"))}
                for o in feedback.get("observations", [])
            ],
            "rubric_levels": feedback.get("rubric_levels", {}),
        }

    def owns_run(self, learner: Learner, run_id: uuid.UUID) -> RunView:
        view = self.usage.run_view(run_id)
        if view is None or view.user_id != learner.user_id or view.purpose not in PURPOSES:
            raise NotFound()
        return view
