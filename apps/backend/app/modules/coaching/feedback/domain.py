"""Validación pura de la salida del evaluador (REQ-02, `docs/arquitectura.md` §8).

La salida del modelo es un dato no confiable. Se acepta solo si:

- Es JSON con las claves conocidas (`status`, `reason`, `observations`, `rubric_levels`);
  una clave de más invalida la salida completa.
- Cada observación trae `criterion` (de la rúbrica), `evidence`, `observation_es` y
  `suggestion_es`. La evidencia debe ser un fragmento literal del texto del alumno
  normalizado (espacios, comillas y guiones; sin distinguir mayúsculas). Una observación
  con evidencia inexistente, criterio desconocido, URL o puntaje de examen se descarta.
- Hay como máximo `max_observations` (3 en escritura, 2 en voz).

Sin observaciones válidas el resultado es "no evaluable", con motivo.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Literal

Status = Literal["evaluable", "not_evaluable"]
NOT_EVALUABLE_REASONS = (
    "too_short",
    "off_topic",
    "other_language",
    "empty",
    "invalid_output",
    "no_valid_evidence",
)
TOP_KEYS = frozenset({"status", "reason", "observations", "rubric_levels"})
OBSERVATION_KEYS = frozenset({"criterion", "evidence", "observation_es", "suggestion_es"})
URL = re.compile(r"(https?://|www\.)\S+", re.IGNORECASE)
EXAM_SCORE = re.compile(
    r"\b\d{1,3}\s*/\s*(6|30|120)\b|\b(toefl|ielts)\s+(score|band)\b|\bpuntaje\b|\bscore\s+of\b",
    re.IGNORECASE,
)
QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"})
MAX_FIELD = 600


@dataclass(frozen=True)
class Observation:
    criterion: str
    evidence: str
    observation_es: str
    suggestion_es: str


@dataclass(frozen=True)
class ValidatedFeedback:
    status: Status
    reason: str | None = None
    observations: tuple[Observation, ...] = ()
    rubric_levels: dict[str, int] = field(default_factory=dict)
    # Lo que el validador descartó, para el reporte del set de evaluación.
    returned_observations: int = 0
    discarded: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "observations": [o.__dict__ for o in self.observations],
            "rubric_levels": dict(self.rubric_levels),
        }


def normalize(text: str) -> str:
    """Normaliza para comparar evidencia: Unicode NFC, comillas y guiones rectos, espacios
    colapsados y sin distinguir mayúsculas."""
    text = unicodedata.normalize("NFC", text).translate(QUOTES)
    return " ".join(text.split()).casefold()


def evidence_in(evidence: str, learner_text: str) -> bool:
    needle = normalize(evidence).strip(" .,;:!?\"'")
    return len(needle) >= 2 and needle in normalize(learner_text)


def not_evaluable(
    reason: str, *, returned: int = 0, discarded: tuple[str, ...] = ()
) -> ValidatedFeedback:
    return ValidatedFeedback(
        status="not_evaluable", reason=reason, returned_observations=returned, discarded=discarded
    )


def parse_output(raw: str | dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def validate(
    raw: str | dict[str, Any],
    *,
    learner_text: str,
    criteria: frozenset[str],
    max_observations: int,
) -> ValidatedFeedback:
    data = parse_output(raw)
    if data is None or not set(data) <= TOP_KEYS or "status" not in data:
        return not_evaluable("invalid_output")
    status = data.get("status")
    if status == "not_evaluable":
        reason = data.get("reason")
        return not_evaluable(reason if reason in NOT_EVALUABLE_REASONS else "invalid_output")
    if status != "evaluable" or not isinstance(data.get("observations", []), list):
        return not_evaluable("invalid_output")
    returned = data.get("observations", [])
    kept: list[Observation] = []
    discarded: list[str] = []
    for item in returned:
        problem = _observation_problem(item, learner_text, criteria)
        if problem is not None:
            discarded.append(problem)
            continue
        if len(kept) >= max_observations:
            discarded.append("over_limit")
            continue
        kept.append(
            Observation(
                criterion=item["criterion"],
                evidence=item["evidence"].strip(),
                observation_es=item["observation_es"].strip(),
                suggestion_es=item["suggestion_es"].strip(),
            )
        )
    if not kept:
        return not_evaluable(
            "no_valid_evidence", returned=len(returned), discarded=tuple(discarded)
        )
    return ValidatedFeedback(
        status="evaluable",
        observations=tuple(kept),
        rubric_levels=_levels(data.get("rubric_levels"), criteria),
        returned_observations=len(returned),
        discarded=tuple(discarded),
    )


def _observation_problem(item: object, learner_text: str, criteria: frozenset[str]) -> str | None:
    if not isinstance(item, dict) or set(item) != OBSERVATION_KEYS:
        return "shape"
    if not all(isinstance(item[k], str) and item[k].strip() for k in OBSERVATION_KEYS):
        return "shape"
    if any(len(item[k]) > MAX_FIELD for k in OBSERVATION_KEYS):
        return "too_long"
    if item["criterion"] not in criteria:
        return "unknown_criterion"
    if any(URL.search(item[k]) for k in OBSERVATION_KEYS):
        return "url"
    if any(EXAM_SCORE.search(item[k]) for k in ("observation_es", "suggestion_es")):
        return "exam_score"
    if not evidence_in(item["evidence"], learner_text):
        return "evidence_not_found"
    return None


def _levels(raw: object, criteria: frozenset[str]) -> dict[str, int]:
    if not isinstance(raw, dict):
        return {}
    return {
        k: v
        for k, v in raw.items()
        if k in criteria and isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 3
    }


def hidden_by_disputes(
    observations: tuple[Observation, ...], disputed_turns: list[str]
) -> tuple[Observation, ...]:
    """Oculta las observaciones cuya evidencia está en un turno disputado (REQ-05, AC-13)."""
    return tuple(
        o for o in observations if not any(evidence_in(o.evidence, turn) for turn in disputed_turns)
    )
