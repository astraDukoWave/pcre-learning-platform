"""Evaluador con Gemini por la API REST (`generateContent`), sin SDK.

`POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` con
`x-goog-api-key`, salida JSON con `responseSchema` y timeout total de 20 s (bajo los 30 s
del router de Heroku). La salida se valida igual en `domain.validate`. Mapeo de errores:

- No se pudo conectar → `EvaluatorFailed` (no se envió: sin costo).
- Respuesta HTTP de error → `EvaluatorFailed("http_<código>")`.
- Timeout o conexión cortada después de enviar → `EvaluatorUnknown`: nunca se reintenta solo.

Solo se construye con `GEMINI_API_KEY` en el servidor (G5) o en `feedback-eval.yml` (G5a).
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.modules.coaching.feedback.ports import (
    EvaluatorFailed,
    EvaluatorReply,
    EvaluatorUnknown,
    FeedbackRequest,
)

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def response_schema(request: FeedbackRequest) -> dict[str, Any]:
    criteria = [c.id for c in request.criteria]
    return {
        "type": "OBJECT",
        "properties": {
            "status": {"type": "STRING", "enum": ["evaluable", "not_evaluable"]},
            "reason": {
                "type": "STRING",
                "nullable": True,
                "enum": ["empty", "too_short", "off_topic", "other_language"],
            },
            "observations": {
                "type": "ARRAY",
                "maxItems": request.max_observations,
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "criterion": {"type": "STRING", "enum": criteria},
                        "evidence": {"type": "STRING"},
                        "observation_es": {"type": "STRING"},
                        "suggestion_es": {"type": "STRING"},
                    },
                    "required": ["criterion", "evidence", "observation_es", "suggestion_es"],
                },
            },
            "rubric_levels": {
                "type": "OBJECT",
                "properties": {c: {"type": "INTEGER"} for c in criteria},
            },
        },
        "required": ["status", "observations"],
    }


class GeminiFeedbackEvaluator:
    provider = "google"

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        max_output_tokens: int = 2048,
        timeout_s: float = 20.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("falta GEMINI_API_KEY")
        if not model:
            raise ValueError("falta GEMINI_MODEL")
        self._key = api_key
        self.model = model
        self.max_output_tokens = max_output_tokens
        self._client = client or httpx.Client(timeout=httpx.Timeout(timeout_s, connect=5.0))

    def evaluate(self, prompt: str, request: FeedbackRequest) -> EvaluatorReply:
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": response_schema(request),
                "maxOutputTokens": self.max_output_tokens,
                "temperature": 0.2,
            },
        }
        started = time.perf_counter()
        try:
            response = self._client.post(
                API_URL.format(model=self.model),
                headers={"x-goog-api-key": self._key, "Content-Type": "application/json"},
                json=body,
            )
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise EvaluatorFailed("connect") from exc
        except httpx.TimeoutException as exc:
            raise EvaluatorUnknown("timeout") from exc
        except httpx.TransportError as exc:
            raise EvaluatorUnknown("connection_lost") from exc
        latency_ms = round((time.perf_counter() - started) * 1000)
        if response.status_code >= 400:
            raise EvaluatorFailed(f"http_{response.status_code}")
        try:
            data = response.json()
        except ValueError as exc:
            raise EvaluatorFailed("invalid_response") from exc
        usage = data.get("usageMetadata") or {}
        return EvaluatorReply(
            raw_text=_text(data),
            model=self.model,
            input_tokens=int(usage.get("promptTokenCount") or 0),
            # Los tokens de razonamiento se facturan como salida.
            output_tokens=int(usage.get("candidatesTokenCount") or 0)
            + int(usage.get("thoughtsTokenCount") or 0),
            latency_ms=latency_ms,
        )


def _text(data: dict[str, Any]) -> str:
    for candidate in data.get("candidates") or []:
        parts = (candidate.get("content") or {}).get("parts") or []
        texts = [p.get("text", "") for p in parts if isinstance(p, dict) and not p.get("thought")]
        if texts:
            return "".join(texts)
    return ""
