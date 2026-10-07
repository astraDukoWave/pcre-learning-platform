"""Rutas de `coaching`: feedback abierto con IA y transcripción. Sin lógica: el formulario
del audio se lee en memoria (`app.http.multipart`) y el servicio corre en el pool de hilos."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from starlette.concurrency import run_in_threadpool

from app.core.errors import ValidationFailed
from app.http.deps import AuthDep, ContainerDep
from app.http.multipart import read_memory_form
from app.modules.coaching.schemas import AiFeedbackOut, TranscriptionOut
from app.modules.coaching.service_feedback import FeedbackFlowService
from app.modules.coaching.service_transcription import TranscriptionFlowService
from app.modules.coaching.stt.domain import MAX_BYTES
from app.modules.practice.service import Learner, PracticeService, check_idempotency_key
from app.modules.usage.service import UsageService

router = APIRouter(prefix="/api/v1", tags=["coaching"])


def get_feedback_flow(container: ContainerDep) -> FeedbackFlowService:
    return FeedbackFlowService(
        container.settings,
        UsageService(container.uow, container.clock, container.settings, container.provider_ready),
        PracticeService(container.uow, container.clock, container.settings),
        container.feedback_evaluator,
    )


FeedbackFlowDep = Annotated[FeedbackFlowService, Depends(get_feedback_flow)]


def get_transcription_flow(container: ContainerDep) -> TranscriptionFlowService:
    return TranscriptionFlowService(
        container.settings,
        UsageService(container.uow, container.clock, container.settings, container.provider_ready),
        PracticeService(container.uow, container.clock, container.settings),
        container.speech_to_text,
    )


TranscriptionFlowDep = Annotated[TranscriptionFlowService, Depends(get_transcription_flow)]


@router.post("/attempts/{attempt_id}/feedback", response_model=AiFeedbackOut)
def request_feedback(
    attempt_id: uuid.UUID,
    ctx: AuthDep,
    flow: FeedbackFlowDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", max_length=80)],
) -> AiFeedbackOut:
    learner = Learner(user_id=ctx.user_id, timezone=ctx.timezone)
    return AiFeedbackOut.model_validate(
        flow.request_feedback(learner, attempt_id, check_idempotency_key(idempotency_key))
    )


TRANSCRIPTION_FORM = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["attempt_id", "activity_id", "duration_ms", "audio"],
                    "properties": {
                        "attempt_id": {"type": "string", "format": "uuid"},
                        "activity_id": {"type": "string", "format": "uuid"},
                        "duration_ms": {"type": "integer", "minimum": 1, "maximum": 60000},
                        "audio": {
                            "type": "string",
                            "format": "binary",
                            "description": "audio/webm (Opus) o audio/mp4; 2 MB y 60 s como máximo",
                        },
                    },
                }
            }
        },
    }
}


@router.post(
    "/speaking/transcriptions", response_model=TranscriptionOut, openapi_extra=TRANSCRIPTION_FORM
)
async def create_transcription(
    request: Request,
    ctx: AuthDep,
    flow: TranscriptionFlowDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", max_length=80)],
) -> TranscriptionOut:
    """Multipart con `attempt_id`, `activity_id`, `duration_ms` y `audio` (WebM u MP4)."""
    key = check_idempotency_key(idempotency_key)
    await run_in_threadpool(flow.ensure_available)  # apagada: no se lee el audio
    form = await read_memory_form(request, max_file_bytes=MAX_BYTES + 1)
    audio = form.files.get("audio")
    try:
        attempt_id = uuid.UUID(form.fields["attempt_id"])
        activity_id = uuid.UUID(form.fields["activity_id"])
        duration_ms = int(form.fields["duration_ms"])
    except (KeyError, ValueError):
        raise ValidationFailed(
            "Faltan attempt_id, activity_id o duration_ms.", code="transcription_fields"
        ) from None
    if audio is None:
        raise ValidationFailed("Falta la grabación.", code="audio_missing")
    learner = Learner(user_id=ctx.user_id, timezone=ctx.timezone)
    result = await run_in_threadpool(
        flow.transcribe,
        learner,
        attempt_id=attempt_id,
        activity_id=activity_id,
        audio=audio.content,
        content_type=audio.content_type,
        duration_ms=duration_ms,
        idempotency_key=key,
    )
    return TranscriptionOut.model_validate(result)
