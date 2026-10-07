"""DTO de las sesiones de voz. Nunca llaves ni configuración del proveedor."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class VoiceSessionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: uuid.UUID
    # Se registra la primera vez (`users.voice_notice_accepted_at`).
    accept_voice_notice: bool = False
    # "Guardar la transcripción y el feedback en mi progreso" (por sesión).
    save_transcript: bool = False


class VoiceAidOut(BaseModel):
    kind: Literal["repeat", "slower", "hint"]
    at_s: float
    text: str | None = None


class VoiceTurnOut(BaseModel):
    n: int
    role: Literal["coach", "learner"]
    text: str
    at_s: float
    aid: bool
    # "Eso no fue lo que dije": problema de reconocimiento, no error del alumno.
    disputed: bool = False


class VoiceObservationOut(BaseModel):
    criterion: str
    criterion_name_es: str
    evidence: str
    observation_es: str
    suggestion_es: str
    # Turno del alumno donde aparece la evidencia (para resaltarla en la transcripción).
    turn: int | None = None


class VoiceFeedbackOut(BaseModel):
    """Feedback final de la sesión (REQ-05): hasta dos observaciones con evidencia. Las que
    tienen evidencia en un turno disputado no se muestran (`hidden` las cuenta)."""

    status: Literal["evaluable", "not_evaluable", "failed", "unknown"]
    reason: str | None = None
    run_id: uuid.UUID | None = None
    label: str | None = None
    observations: list[VoiceObservationOut] = []
    rubric_levels: dict[str, int] = {}
    hidden: int = 0


class VoiceSessionOut(BaseModel):
    id: uuid.UUID
    scenario_id: uuid.UUID
    status: Literal["reserved", "active", "ended", "failed", "expired"]
    ws_path: str
    max_seconds: int
    save_transcript: bool
    created_at: datetime
    deadline_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    end_reason: str | None
    duration_s: int | None
    learner_speech_s: float
    aids: list[VoiceAidOut]
    transcript: list[VoiceTurnOut] | None
    feedback: VoiceFeedbackOut | None
