"""Puerto de transcripción (ADR-09, `docs/arquitectura.md` §8): 15 s, sin reintentos."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Word:
    text: str
    confidence: float


@dataclass(frozen=True)
class Transcription:
    text: str
    words: tuple[Word, ...]
    duration_s: float
    model: str
    latency_ms: int


class SttFailed(Exception):
    """No se envió o el proveedor respondió con un error: sin costo, se puede reintentar."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class SttUnknown(Exception):
    """Se envió y no hubo respuesta: resultado desconocido, nunca se reintenta solo."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class SpeechToText(Protocol):
    provider: str
    model: str

    def transcribe(self, audio: bytes, content_type: str) -> Transcription: ...
