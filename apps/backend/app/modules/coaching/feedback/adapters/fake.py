"""Evaluador de feedback determinista para pruebas, E2E y desarrollo (`FEEDBACK_PROVIDER=fake`;
nunca en producción). No llama a ningún proveedor.

Comportamiento:
- Menos de 8 palabras → `not_evaluable/too_short`; mayoría de palabras en español →
  `not_evaluable/other_language`.
- Si no, una observación por criterio (hasta el máximo) citando literalmente el inicio de
  una oración distinta del texto (los turnos de voz, separados por ` | `, cuentan como
  oraciones).
- Marcadores para pruebas en el texto del alumno: `[[fake:failed]]` (error del proveedor),
  `[[fake:unknown]]` (timeout tras enviar), `[[fake:invented]]` (evidencia inventada) y
  `[[fake:url]]` (una sugerencia con enlace).
"""

from __future__ import annotations

import json
import re

from app.modules.coaching.feedback.ports import (
    EvaluatorFailed,
    EvaluatorReply,
    EvaluatorUnknown,
    FeedbackRequest,
)

SPANISH = frozenset(
    [
        "el",
        "la",
        "los",
        "las",
        "de",
        "que",
        "y",
        "en",
        "un",
        "una",
        "por",
        "para",
        "con",
        "no",
        "es",
        "se",
        "lo",
        "como",
        "pero",
        "porque",
        "mi",
        "muy",
    ]
)
SENTENCE = re.compile(r"[^.!?\n|]+[.!?]?")


class FakeFeedbackEvaluator:
    provider = "fake"
    model = "fake-evaluator-1"
    max_output_tokens = 512

    def __init__(self) -> None:
        self.calls: list[FeedbackRequest] = []

    def evaluate(self, prompt: str, request: FeedbackRequest) -> EvaluatorReply:
        self.calls.append(request)
        text = request.learner_text
        if "[[fake:failed]]" in text:
            raise EvaluatorFailed("http_503")
        if "[[fake:unknown]]" in text:
            raise EvaluatorUnknown("timeout")
        output = self._output(text, request)
        raw = json.dumps(output, ensure_ascii=False)
        return EvaluatorReply(
            raw_text=raw,
            model=self.model,
            input_tokens=len(prompt) // 4,
            output_tokens=len(raw) // 4,
            latency_ms=5,
        )

    def _output(self, text: str, request: FeedbackRequest) -> dict[str, object]:
        words = re.findall(r"[A-Za-zÁÉÍÓÚáéíóúñÑ']+", text)
        if len(words) < 8:
            return {"status": "not_evaluable", "reason": "too_short", "observations": []}
        if sum(w.lower() in SPANISH for w in words) > len(words) / 3:
            return {"status": "not_evaluable", "reason": "other_language", "observations": []}
        sentences = [s.strip() for s in SENTENCE.findall(text) if len(s.split()) >= 3]
        observations: list[dict[str, str]] = []
        for criterion, sentence in zip(request.criteria, sentences, strict=False):
            if len(observations) >= request.max_observations:
                break
            evidence = " ".join(sentence.split()[:4])
            suggestion = "Prueba una versión más precisa de esta frase."
            if "[[fake:url]]" in text:
                suggestion += " Más en https://example.com/guia"
            observations.append(
                {
                    "criterion": criterion.id,
                    "evidence": "I has went there" if "[[fake:invented]]" in text else evidence,
                    "observation_es": f"Esta frase apoya el criterio «{criterion.name_es}».",
                    "suggestion_es": suggestion,
                }
            )
        return {
            "status": "evaluable",
            "reason": None,
            "observations": observations,
            "rubric_levels": {c.id: 2 for c in request.criteria},
        }
