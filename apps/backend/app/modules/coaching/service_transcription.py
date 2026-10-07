"""Transcripción de grabaciones (MVP-02 REQ-04).

Flujo: capacidad `stt` encendida → grabación propia de práctica que lo admite → límites del
audio (tipo, 2 MB, 60 s declarados) → ejecución previa (la misma clave devuelve lo mismo; solo
se repite tras `failed`) → reserva del peor caso (60.5 s × precio) → Nova-3 (15 s) →
conciliación por la duración real → guardado en el intento. El audio solo vive en memoria:
llega en `bytes`, se envía y se descarta; nunca se guarda ni se registra.

- Repetición: "Palabras reconocidas: 7 de 9" con las faltantes; guarda `recognized_ratio`, sin
  tocar la evaluación.
- Entrevista: "Esto entendimos: …"; el alumno confirma o dice "Eso no fue lo que dije". Solo
  una transcripción confirmada recibe feedback (REQ-02, `FeedbackFlowService`).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Final

from app.core.config import Settings
from app.core.errors import AppError, Conflict
from app.modules.coaching.stt import domain
from app.modules.coaching.stt.ports import SpeechToText, SttFailed, SttUnknown, Transcription
from app.modules.practice.service import Learner, PracticeService, TranscriptionTarget
from app.modules.usage.service import CapabilityDisabled, RunView, UsageService

logger = logging.getLogger("app.coaching")

PURPOSE: Final = "transcription"
HINT_ES = (
    "Si dijiste estas palabras y no aparecen, puede ser el reconocimiento; escucha el modelo y "
    "vuelve a intentarlo."
)


class AudioTooLarge(AppError):
    status_code = 413
    code = "too_large"


class AudioInvalid(AppError):
    status_code = 422
    code = "audio_invalid"


def reject(exc: domain.AudioRejected) -> AppError:
    if exc.code == "too_large":
        return AudioTooLarge(exc.message)
    return AudioInvalid(exc.message, code=exc.code)


class TranscriptionFlowService:
    def __init__(
        self,
        settings: Settings,
        usage: UsageService,
        practice: PracticeService,
        stt: SpeechToText | None,
    ) -> None:
        self.settings = settings
        self.usage = usage
        self.practice = practice
        self.stt = stt

    def ensure_available(self) -> None:
        """Antes de leer el audio: con la capacidad apagada no se recibe nada."""
        self.usage.require("stt")
        if self.stt is None:
            raise CapabilityDisabled()

    def transcribe(
        self,
        learner: Learner,
        *,
        attempt_id: uuid.UUID,
        activity_id: uuid.UUID,
        audio: bytes,
        content_type: str,
        duration_ms: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self.ensure_available()
        target = self.practice.transcription_target(learner, attempt_id, activity_id)
        try:
            base_type = domain.check_audio(content_type, len(audio), duration_ms)
        except domain.AudioRejected as exc:
            raise reject(exc) from None
        same_key = self.usage.run_by_key(learner.user_id, PURPOSE, idempotency_key)
        if same_key is not None:
            if same_key.attempt_id != attempt_id:
                raise Conflict(
                    "Esta clave ya se usó con otra grabación.", code="idempotency_conflict"
                )
            return self._from_run(same_key, target)
        latest = self.usage.latest_for_attempt(learner.user_id, attempt_id, (PURPOSE,))
        if latest is not None and latest.status != "failed":
            return self._from_run(latest, target)  # sin otra llamada ni otro cobro
        return self._call(learner, target, audio, base_type, idempotency_key)

    def _call(
        self,
        learner: Learner,
        target: TranscriptionTarget,
        audio: bytes,
        content_type: str,
        key: str,
    ) -> dict[str, Any]:
        stt = self.stt
        assert stt is not None
        price = self.settings.stt_price_per_min_microusd
        reservation = self.usage.reserve(
            learner.user_id,
            purpose=PURPOSE,
            amount=domain.max_cost_microusd(price),
            idempotency_key=key,
            provider=stt.provider,
            model=stt.model,
            attempt_id=target.attempt_id,
        )
        if reservation.existing:  # otra petición con la misma clave llegó primero
            view = self.usage.run_view(reservation.run_id)
            assert view is not None
            return self._from_run(view, target)
        run_id = reservation.run_id
        self.usage.mark_running(run_id)
        try:
            result = stt.transcribe(audio, content_type)
        except SttFailed as exc:
            self.usage.release(run_id, error_code=exc.code)
            logger.warning("transcription_failed", extra={"error_code": exc.code})
            return self._shown(run_id, target, {"status": "failed", "reason": exc.code})
        except SttUnknown as exc:
            self.usage.mark_unknown(run_id, error_code=exc.code)
            return self._shown(run_id, target, {"status": "unknown", "reason": exc.code})
        except Exception:
            # Un error propio después de enviar: no se supone consumo cero.
            self.usage.mark_unknown(run_id, error_code="internal_error")
            raise
        # Sin duración del proveedor se concilia al peor caso reservado.
        billed_s = result.duration_s if result.duration_s > 0 else domain.MAX_SECONDS + 1
        output = self._output(target, result)
        self.usage.settle(
            run_id,
            cost=domain.cost_microusd(billed_s, price),
            observed_units=round(billed_s),
            output=output,
            latency_ms=result.latency_ms,
            error_code="too_long" if output["status"] == "too_long" else None,
        )
        shown = self._shown(run_id, target, output)
        if output["status"] == "transcribed":
            stored = {k: v for k, v in shown.items() if k not in ("run_id", "attempt_id")}
            self.practice.store_transcription(
                learner, target.attempt_id, {**stored, "run_id": str(run_id)}
            )
        return shown

    def _output(self, target: TranscriptionTarget, result: Transcription) -> dict[str, Any]:
        if domain.too_long(result.duration_s):
            # Se transcribió (y se cobra), pero pasó de 60 s: no se muestra ni se guarda.
            return {"status": "too_long", "reason": "too_long"}
        out: dict[str, Any] = {
            "status": "transcribed",
            "kind": "repeat" if target.subtype == "listen_and_repeat" else "interview",
            "text": result.text,
            "words": [{"word": w.text, "confidence": round(w.confidence, 3)} for w in result.words],
            "duration_s": round(result.duration_s, 2),
        }
        if out["kind"] == "repeat":
            out["repeat"] = domain.compare_repeat(
                target.target_sentence or "", result.text
            ).as_dict()
        else:
            out["confirmed"] = False
            out["disputed"] = False
        return out

    def _from_run(self, run: RunView, target: TranscriptionTarget) -> dict[str, Any]:
        if run.status in ("reserved", "running"):
            raise Conflict(
                "La transcripción anterior sigue en curso.", code="transcription_in_progress"
            )
        if run.status == "succeeded" and run.output is not None:
            return self._shown(run.id, target, run.output)
        status = "unknown" if run.status == "unknown" else "failed"
        return self._shown(run.id, target, {"status": status, "reason": run.error_code})

    def _shown(
        self, run_id: uuid.UUID, target: TranscriptionTarget, output: dict[str, Any]
    ) -> dict[str, Any]:
        if output.get("status") == "too_long":
            raise AudioInvalid("La grabación debe durar 60 segundos o menos.", code="too_long")
        shown = {
            "run_id": run_id,
            "attempt_id": target.attempt_id,
            "status": output.get("status"),
            "reason": output.get("reason"),
            "kind": output.get("kind"),
            "text": output.get("text"),
            "words": output.get("words", []),
            "repeat": output.get("repeat"),
            "confirmed": output.get("confirmed"),
            "disputed": output.get("disputed"),
        }
        if shown["repeat"] is not None:
            shown["hint_es"] = HINT_ES
        return shown
