"""Validación pura de la salida del evaluador (REQ-02, `docs/arquitectura.md` §8).

La salida del modelo es un dato no confiable. Se acepta solo si:

- Es JSON con las claves conocidas (`status`, `reason`, `observations`, `rubric_levels`);
  una clave de más invalida la salida completa.
- Cada observación trae `criterion` (de la rúbrica), `evidence`, `observation_es` y
  `suggestion_es`. La evidencia debe ser un fragmento literal del texto del alumno
  normalizado (espacios, comillas y guiones; sin distinguir mayúsculas). Una observación
  con evidencia inexistente, criterio desconocido, URL o puntaje de examen se descarta.
- Hay como máximo `max_observations`, acotado por tipo (`MAX_OBSERVATIONS`: 3 en escritura y
  entrevista, 2 en voz).
- `observation_es` y `suggestion_es` no traen URLs (con o sin esquema) ni correos, ni dan
  puntajes de examen, bandas, calificaciones o niveles del MCER. La evidencia sí puede citar un
  enlace que escribió el alumno: es literal.

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
MAX_OBSERVATIONS = {"writing": 3, "interview": 3, "voice": 2}
TLDS = (
    "com|net|org|edu|gov|info|io|co|uk|us|ca|au|es|mx|ar|cl|pe|de|fr|it|be|ly|me|app|dev|ai"
    "|tv|gl|to|link|site|online"
)
URL = re.compile(
    r"(https?://|www\.)\S+"  # con esquema o www
    r"|[\w.+-]+@[\w-]+(\.[\w-]+)+"  # correo
    r"|\b[a-z0-9-]+(\.[a-z0-9-]+)+/\S*"  # dominio con ruta: bit.ly/x1
    rf"|\b([a-z0-9-]+\.)+({TLDS})\b",  # dominio con un TLD común: example.com
    re.IGNORECASE,
)
EXAM_SCORE = re.compile(
    r"\b\d{1,3}\s*(/|\bde\b|\bsobre\b|\bout\s+of\b)\s*\d{1,3}\b"  # 6/6, 5 de 6, 25 sobre 30
    r"|\b(toefl|ielts|cambridge)\s+(score|band)\b|\bscore\s*(of\b|[:=]?\s*\d)"
    r"|\bband[as]?\s*\d|\bpuntaje|\bpuntuaci[oó]n|\bcalificaci[oó]n|\bnota\s+(de\s+)?\d"
    r"|\b\d{1,3}\s+puntos\b|\b(nivel|level)\s+(del?\s+)?(mcer\s+|cefr\s+)?[abc][12]\b",
    re.IGNORECASE,
)
CEFR = re.compile(r"\b[ABC][12]\b")  # B2 suelto; en mayúsculas para no tocar «a1» u otras
QUOTES = str.maketrans(
    {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "‹": "<", "›": ">"}
)
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
    """Normaliza para comparar evidencia: Unicode NFKC, comillas y guiones rectos, los ‹ › que
    pone el delimitador del prompt vuelven a ser < >, espacios colapsados y sin distinguir
    mayúsculas."""
    text = unicodedata.normalize("NFKC", text).translate(QUOTES)
    return " ".join(text.split()).casefold()


def evidence_in(evidence: str, learner_text: str) -> bool:
    """La evidencia es un fragmento literal de palabras completas del texto del alumno: «is»
    no cuenta como cita de «this»."""
    needle = normalize(evidence).strip(" .,;:!?\"'")
    if not any(ch.isalnum() for ch in needle) or len(needle) < 2:
        return False
    pattern = rf"(?<!\w){re.escape(needle)}(?!\w)"
    return re.search(pattern, normalize(learner_text)) is not None


def observation_cap(kind: str, requested: int) -> int:
    """Tope de observaciones: el pedido, nunca más que el del tipo (2 en voz)."""
    return min(requested, MAX_OBSERVATIONS[kind])


def forbidden_content(text: str) -> str | None:
    """`url` o `exam_score` si un texto para el alumno trae un enlace o un puntaje."""
    if URL.search(text):
        return "url"
    if EXAM_SCORE.search(text) or CEFR.search(text):
        return "exam_score"
    return None


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
    # La evidencia puede citar un enlace que el alumno escribió (es literal); lo que se le
    # muestra como observación o sugerencia nunca trae enlaces ni puntajes.
    for key in ("observation_es", "suggestion_es"):
        problem = forbidden_content(item[key])
        if problem is not None:
            return problem
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


def visible_after_disputes(
    observations: tuple[Observation, ...], turns: list[str], disputed: set[int]
) -> tuple[Observation, ...]:
    """Observaciones que siguen visibles tras disputar turnos (REQ-05, AC-13): la evidencia debe
    estar completa dentro de un turno no disputado y en ninguno disputado. Una evidencia que
    cruza turnos (` | `) no está completa en ninguno y se oculta."""
    kept = [t for i, t in enumerate(turns) if i not in disputed]
    hidden = [t for i, t in enumerate(turns) if i in disputed]
    return tuple(
        o
        for o in observations
        if any(evidence_in(o.evidence, t) for t in kept)
        and not any(evidence_in(o.evidence, t) for t in hidden)
    )
