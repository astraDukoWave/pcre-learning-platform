"""Doble de `TextToSpeech` para pruebas y `--dry-run`: no usa la red. El lint rechaza
audio de este proveedor dentro de `content/` (`audio_provider`)."""

from __future__ import annotations

import hashlib

from app.modules.content.ports import SpeechSegment


class FakeTextToSpeech:
    provider = "fake"
    model = "fake-tts"

    def __init__(self) -> None:
        self.calls: list[SpeechSegment] = []

    def synthesize(self, segment: SpeechSegment) -> bytes:
        self.calls.append(segment)
        return b"FAKE-" + hashlib.sha256(f"{segment.voice}:{segment.text}".encode()).digest()
