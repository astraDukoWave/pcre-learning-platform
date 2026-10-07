"""DTO de las sesiones de voz. Nunca llaves ni configuración del proveedor."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

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
    aids: list[VoiceAidOut]
    transcript: list[VoiceTurnOut] | None
    feedback: dict[str, Any] | None
