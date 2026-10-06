"""Puertos del módulo de contenido."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SpeechSegment:
    speaker: str
    voice: str
    text: str
    pause_after_ms: int = 0


class TextToSpeech(Protocol):
    """Genera audio del contenido (ADR-12). Solo corre en el workflow aprobado
    `content-audio.yml`; la app en ejecución nunca llama a un TTS."""

    provider: str
    model: str

    def synthesize(self, segment: SpeechSegment) -> bytes: ...
