"""Corrección determinista en el servidor (REQ-10, REQ-11, ADR-09) y reglas de idempotencia.

Recibe la respuesta del alumno y la parte privada de la actividad (`solution`) como datos
planos; no conoce ORM, HTTP ni Pydantic.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

AUTO_GRADED = frozenset({"choice", "word_completion", "sentence_order", "guided_dialogue"})
SELF_ASSESSED = frozenset({"short_writing", "recorded_speaking"})
AID_KINDS = ("hint", "support_es", "transcript", "example")
MAX_TEXT = 4000


class InvalidResponse(ValueError):
    """La forma de la respuesta no corresponde al formato (422)."""


@dataclass(frozen=True)
class Grade:
    evaluation_status: str  # evaluated | not_evaluable | pending
    evaluation_source: str  # auto | self
    score: float | None
    correct: bool | None
    result: dict[str, Any] = field(default_factory=dict)


def _ids(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise InvalidResponse(f"`{field_name}` debe ser una lista de textos")
    return value


def grade_choice(
    response: dict[str, Any], public: dict[str, Any], solution: dict[str, Any]
) -> Grade:
    selected = _ids(response.get("selected"), "selected")
    valid = {o["id"] for o in public["options"]}
    if not selected or not set(selected) <= valid or len(set(selected)) != len(selected):
        raise InvalidResponse("elige una opción válida")
    if not public.get("multiple") and len(selected) != 1:
        raise InvalidResponse("elige una sola opción")
    correct_ids = set(solution["correct"])
    is_correct = set(selected) == correct_ids
    why = solution.get("why", {})
    return Grade(
        evaluation_status="evaluated",
        evaluation_source="auto",
        score=1.0 if is_correct else 0.0,
        correct=is_correct,
        result={
            "selected": selected,
            "correct_options": sorted(correct_ids),
            "option_feedback": {i: why[i] for i in selected if i in why},
        },
    )


def normalize_text(value: str, *, case_sensitive: bool = False) -> str:
    text = unicodedata.normalize("NFKC", value).strip()
    text = text.replace("’", "'").replace("‘", "'")
    text = re.sub(r"\s+", " ", text)
    return text if case_sensitive else text.lower()


def grade_word_completion(
    response: dict[str, Any], public: dict[str, Any], solution: dict[str, Any]
) -> Grade:
    answers = response.get("answers")
    if not isinstance(answers, dict):
        raise InvalidResponse("`answers` debe ser un objeto {hueco: texto}")
    gaps = {g["id"]: g for g in solution["gaps"]}
    shown = {g["id"]: g["shown"] for g in public["gaps"]}
    if set(answers) != set(gaps):
        raise InvalidResponse("responde todos los huecos")
    per_gap: dict[str, bool] = {}
    for gap_id, raw in answers.items():
        if not isinstance(raw, str) or len(raw) > 60:
            raise InvalidResponse("cada hueco lleva un texto breve")
        gap = gaps[gap_id]
        cs = bool(gap.get("case_sensitive"))
        typed = normalize_text(raw, case_sensitive=cs)
        prefix = normalize_text(shown[gap_id], case_sensitive=cs)
        # El alumno puede escribir la palabra completa o solo lo que falta.
        candidates = {typed, normalize_text(shown[gap_id] + raw, case_sensitive=cs)}
        if typed.startswith(prefix):
            candidates.add(typed)
        accepted = {normalize_text(a, case_sensitive=cs) for a in gap["accepted"]}
        per_gap[gap_id] = bool(candidates & accepted)
    correct_count = sum(per_gap.values())
    return Grade(
        evaluation_status="evaluated",
        evaluation_source="auto",
        score=correct_count / len(per_gap),
        correct=correct_count == len(per_gap),
        result={
            "per_gap": per_gap,
            "accepted": {g: list(gaps[g]["accepted"]) for g in gaps},
        },
    )


def grade_sentence_order(
    response: dict[str, Any], public: dict[str, Any], solution: dict[str, Any]
) -> Grade:
    order = _ids(response.get("order"), "order")
    if sorted(order) != sorted(public["tokens"]):
        raise InvalidResponse("usa todas las fichas una vez")
    accepted = [list(o) for o in solution["accepted_orders"]]
    is_correct = order in accepted
    return Grade(
        evaluation_status="evaluated",
        evaluation_source="auto",
        score=1.0 if is_correct else 0.0,
        correct=is_correct,
        result={"order": order, "correct_order": accepted[0]},
    )


def grade_guided_dialogue(
    response: dict[str, Any], public: dict[str, Any], solution: dict[str, Any]
) -> Grade:
    path = _ids(response.get("path"), "path")
    nodes = {n["id"]: n for n in public["nodes"]}
    current: str | None = public["start"]
    walked: list[str] = []
    for step in path:
        if current is None:
            raise InvalidResponse("el diálogo ya terminó")
        node_id, _, option_id = step.partition(".")
        if node_id != current:
            raise InvalidResponse("el camino no sigue el diálogo")
        option = next((o for o in nodes[node_id]["options"] if o["id"] == option_id), None)
        if option is None:
            raise InvalidResponse("opción inexistente")
        walked.append(step)
        current = option.get("next")
        if current is not None and not nodes[current]["options"]:
            current = None
    if current is not None and nodes[current]["options"]:
        raise InvalidResponse("termina el diálogo antes de enviar")
    options = solution["options"]
    feedback = [
        {"step": s, "feedback_es": options[s]["feedback_es"], "good": options[s]["good"]}
        for s in walked
    ]
    good = sum(1 for f in feedback if f["good"])
    success = any(all(s in walked for s in p) for p in solution["success_paths"])
    return Grade(
        evaluation_status="evaluated",
        evaluation_source="auto",
        score=good / len(feedback) if feedback else 0.0,
        correct=success,
        result={"turns": feedback, "success": success},
    )


def _self_assessment(response: dict[str, Any], rubric: dict[str, Any] | None) -> dict[str, int]:
    raw = response.get("self_assessment")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise InvalidResponse("`self_assessment` debe ser un objeto {criterio: 0–3}")
    criteria = {c["id"] for c in (rubric or {}).get("criteria", [])}
    out: dict[str, int] = {}
    for key, value in raw.items():
        if key not in criteria or not isinstance(value, int) or not 0 <= value <= 3:
            raise InvalidResponse("cada criterio se marca de 0 a 3")
        out[key] = value
    return out


def grade_short_writing(
    response: dict[str, Any], public: dict[str, Any], rubric: dict[str, Any] | None
) -> Grade:
    text = response.get("text")
    if not isinstance(text, str) or not text.strip():
        raise InvalidResponse("escribe tu respuesta")
    if len(text) > MAX_TEXT:
        raise InvalidResponse("la respuesta puede tener como máximo 4 000 caracteres")
    words = len(text.split())
    scores = _self_assessment(response, rubric)
    return Grade(
        evaluation_status="evaluated" if scores else "pending",
        evaluation_source="self",
        score=(sum(scores.values()) / (3 * len(scores))) if scores else None,
        correct=None,
        result={
            "words": words,
            "within_limits": public["min_words"] <= words <= public["max_words"],
            "self_assessment": scores,
        },
    )


def grade_recorded_speaking(response: dict[str, Any], rubric: dict[str, Any] | None) -> Grade:
    recorded = response.get("recorded")
    if not isinstance(recorded, bool):
        raise InvalidResponse("indica si pudiste grabar")
    scores = _self_assessment(response, rubric)
    if not recorded:
        return Grade(
            "not_evaluable", "self", None, None, {"recorded": False, "reason": "no_recording"}
        )
    return Grade(
        evaluation_status="evaluated" if scores else "pending",
        evaluation_source="self",
        score=(sum(scores.values()) / (3 * len(scores))) if scores else None,
        correct=None,
        result={"recorded": True, "self_assessment": scores},
    )


def self_assess(
    fmt: str,
    evaluation_status: str,
    result: dict[str, Any],
    raw: Any,
    rubric: dict[str, Any] | None,
) -> Grade:
    """Autoevaluación posterior al envío (REQ-10): el alumno ve la rúbrica después de
    enviar y marca cada criterio de 0 a 3. Solo cierra una producción `pending`; no toca la
    respuesta guardada."""
    if fmt not in SELF_ASSESSED:
        raise InvalidResponse("esta actividad se corrige automáticamente")
    if evaluation_status == "not_evaluable":
        raise InvalidResponse("no hay grabación que evaluar")
    scores = _self_assessment({"self_assessment": raw}, rubric)
    criteria = {c["id"] for c in (rubric or {}).get("criteria", [])}
    if not criteria or set(scores) != criteria:
        raise InvalidResponse("marca todos los criterios de la rúbrica")
    return Grade(
        evaluation_status="evaluated",
        evaluation_source="self",
        score=sum(scores.values()) / (3 * len(scores)),
        correct=None,
        result={**result, "self_assessment": scores},
    )


def grade(
    fmt: str,
    response: dict[str, Any],
    public: dict[str, Any],
    solution: dict[str, Any],
    rubric: dict[str, Any] | None,
) -> Grade:
    if not isinstance(response, dict):
        raise InvalidResponse("la respuesta debe ser un objeto")
    if fmt == "choice":
        return grade_choice(response, public, solution)
    if fmt == "word_completion":
        return grade_word_completion(response, public, solution)
    if fmt == "sentence_order":
        return grade_sentence_order(response, public, solution)
    if fmt == "guided_dialogue":
        return grade_guided_dialogue(response, public, solution)
    if fmt == "short_writing":
        return grade_short_writing(response, public, rubric)
    if fmt == "recorded_speaking":
        return grade_recorded_speaking(response, rubric)
    raise InvalidResponse(f"formato desconocido: {fmt}")


def request_hash(payload: dict[str, Any]) -> str:
    """Huella del cuerpo para la idempotencia: misma clave + mismo cuerpo → misma respuesta."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def local_day(now: datetime, timezone: str) -> date:
    """Día local del alumno al enviar (la racha usa este valor; EDGE-10)."""
    try:
        return now.astimezone(ZoneInfo(timezone)).date()
    except (ZoneInfoNotFoundError, ValueError):
        return now.astimezone(ZoneInfo("America/Mexico_City")).date()


def lesson_completed(practice_activity_ids: set[str], attempted_ids: set[str]) -> bool:
    """Completa cuando todas las actividades del pool `practice` se enviaron al menos una
    vez. Completar no significa acertar."""
    return bool(practice_activity_ids) and practice_activity_ids <= attempted_ids
