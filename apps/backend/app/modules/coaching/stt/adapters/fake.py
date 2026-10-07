"""Transcriptor determinista para pruebas, E2E y desarrollo (`STT_PROVIDER=fake`; nunca en
producción). No llama a ningún proveedor ni guarda el audio.

- Si el audio empieza con `FAKE:` (pruebas), el resto es la transcripción; `FAKE:!failed` y
  `FAKE:!unknown` simulan los errores; `FAKE:!long` simula 75 s de audio.
- Con audio real (E2E con micrófono falso) devuelve `default_text`.
"""

from __future__ import annotations

from app.modules.coaching.stt.ports import SttFailed, SttUnknown, Transcription, Word

DEFAULT_TEXT = "Hi, my name is Daniela and I work at a agency."


class FakeSpeechToText:
    provider = "fake"
    model = "fake-stt-1"

    def __init__(self, default_text: str = DEFAULT_TEXT) -> None:
        self.default_text = default_text
        self.calls = 0

    def transcribe(self, audio: bytes, content_type: str) -> Transcription:
        self.calls += 1
        duration = 8.0
        text = self.default_text
        if audio.startswith(b"FAKE:"):
            text = audio[5:].split(b"\n", 1)[0].decode("utf-8", errors="replace")
            if text == "!failed":
                raise SttFailed("http_503")
            if text == "!unknown":
                raise SttUnknown("timeout")
            if text == "!long":
                text, duration = "This answer went on for far too long.", 75.0
        return Transcription(
            text=text,
            words=tuple(Word(text=w, confidence=0.9) for w in text.split()),
            duration_s=duration,
            model=self.model,
            latency_ms=3,
        )
