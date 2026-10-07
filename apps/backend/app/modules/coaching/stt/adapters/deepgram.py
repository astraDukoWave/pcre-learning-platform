"""Deepgram Nova-3 pregrabado por REST (`POST /v1/listen`), sin SDK.

`model=nova-3`, `language=en`, `smart_format=true`, `punctuate=true`, cuerpo binario con su
`Content-Type` y `Authorization: Token <DEEPGRAM_API_KEY>`; plazo total de 15 s
(`app.core.deadline`). El audio solo viaja en memoria. Precio de referencia: USD 0.0043 por
minuto (deepgram.com/pricing, 5 oct 2026; se reconfirma en G5). Errores:

- No se pudo conectar, la llamada no salió de la cola o HTTP de error → `SttFailed` (sin
  costo).
- Timeout, plazo vencido, conexión cortada o un 200 ilegible → `SttUnknown`: se envió y pudo
  facturarse; nunca se reintenta solo.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.deadline import DeadlineExceeded, call_with_deadline
from app.modules.coaching.stt.ports import SttFailed, SttUnknown, Transcription, Word

LISTEN_URL = "https://api.deepgram.com/v1/listen"


class DeepgramSpeechToText:
    provider = "deepgram"
    model = "nova-3"

    def __init__(
        self, api_key: str, *, timeout_s: float = 15.0, client: httpx.Client | None = None
    ) -> None:
        if not api_key:
            raise ValueError("falta DEEPGRAM_API_KEY")
        self._key = api_key
        self.timeout_s = timeout_s
        self._client = client or httpx.Client(timeout=httpx.Timeout(timeout_s, connect=5.0))

    def transcribe(self, audio: bytes, content_type: str) -> Transcription:
        started = time.perf_counter()
        try:
            response = call_with_deadline(lambda: self._post(audio, content_type), self.timeout_s)
        except DeadlineExceeded as exc:
            raise (SttUnknown("timeout") if exc.started else SttFailed("busy")) from exc
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise SttFailed("connect") from exc
        except httpx.TimeoutException as exc:
            raise SttUnknown("timeout") from exc
        except httpx.HTTPError as exc:
            raise SttUnknown("connection_lost") from exc
        latency_ms = round((time.perf_counter() - started) * 1000)
        if response.status_code >= 400:
            raise SttFailed(f"http_{response.status_code}")
        try:
            return _parse(response.json(), self.model, latency_ms)
        except (ValueError, TypeError, AttributeError) as exc:
            raise SttUnknown("invalid_response") from exc

    def _post(self, audio: bytes, content_type: str) -> httpx.Response:
        return self._client.post(
            LISTEN_URL,
            params={
                "model": self.model,
                "language": "en",
                "smart_format": "true",
                "punctuate": "true",
            },
            headers={"Authorization": f"Token {self._key}", "Content-Type": content_type},
            content=audio,
        )


def _parse(data: dict[str, Any], model: str, latency_ms: int) -> Transcription:
    alt = _first_alternative(data)
    return Transcription(
        text=str(alt.get("transcript") or ""),
        words=tuple(
            Word(
                text=str(w.get("punctuated_word") or w.get("word") or ""),
                confidence=float(w.get("confidence") or 0.0),
            )
            for w in alt.get("words") or []
        ),
        duration_s=float((data.get("metadata") or {}).get("duration") or 0.0),
        model=model,
        latency_ms=latency_ms,
    )


def _first_alternative(data: dict[str, Any]) -> dict[str, Any]:
    channels = (data.get("results") or {}).get("channels") or []
    for channel in channels:
        for alt in channel.get("alternatives") or []:
            if isinstance(alt, dict):
                return alt
    return {}
