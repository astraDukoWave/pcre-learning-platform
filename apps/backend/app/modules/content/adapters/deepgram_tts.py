"""Adaptador de Deepgram Aura-2 (TTS) para `scripts/content/generate_audio.py`.

`POST https://api.deepgram.com/v1/speak?model=<voz>&encoding=mp3&bit_rate=48000` con
`{"text": …}` y `Authorization: Token <DEEPGRAM_API_KEY>`. Solo lo construye el script
del workflow `content-audio.yml` (environment con aprobación). Precio de referencia: USD
0.030 por 1 000 caracteres (5 oct 2026; se reconfirma en G2).
"""

from __future__ import annotations

import httpx

from app.modules.content.ports import SpeechSegment

SPEAK_URL = "https://api.deepgram.com/v1/speak"


class DeepgramTextToSpeech:
    provider = "deepgram"
    model = "aura-2"

    def __init__(
        self, api_key: str, *, client: httpx.Client | None = None, timeout_s: float = 30
    ) -> None:
        if not api_key:
            raise ValueError("falta DEEPGRAM_API_KEY")
        self._key = api_key
        self._client = client or httpx.Client(timeout=timeout_s)

    def synthesize(self, segment: SpeechSegment) -> bytes:
        response = self._client.post(
            SPEAK_URL,
            params={"model": segment.voice, "encoding": "mp3", "bit_rate": 48000},
            headers={"Authorization": f"Token {self._key}", "Content-Type": "application/json"},
            json={"text": segment.text},
        )
        response.raise_for_status()
        if not response.headers.get("content-type", "").startswith("audio/"):
            raise RuntimeError("Deepgram no devolvió audio")
        return response.content
