"""Prompts versionados del evaluador (REQ-02). Cambiar un texto exige una versión nueva: la
versión viaja en `ai_runs.prompt_version` y en el reporte del set de evaluación."""

from __future__ import annotations

import hashlib
import unicodedata
from pathlib import Path

from app.modules.coaching.feedback.domain import observation_cap
from app.modules.coaching.feedback.ports import FeedbackRequest

HERE = Path(__file__).parent
VERSIONS = {"writing": "writing-v1", "interview": "interview-v1", "voice": "voice-v1"}
_FILES = {
    "writing-v1": "writing_v1.txt",
    "interview-v1": "interview_v1.txt",
    "voice-v1": "voice_v1.txt",
}


ANGLES = str.maketrans({"<": "‹", ">": "›", "〈": "‹", "〉": "›", "⟨": "‹", "⟩": "›"})


def delimit(learner_text: str) -> str:
    """El texto del alumno no puede cerrar el delimitador ni abrir otro: se normaliza a NFKC
    (los ＜ ＞ de ancho completo pasan a < >) y los signos de ángulo pasan a ‹ ›."""
    return unicodedata.normalize("NFKC", learner_text).translate(ANGLES)


def boundary(learner_text: str) -> str:
    """Nombre del bloque con un sufijo que sale del propio texto: el alumno no puede escribir
    el cierre porque no conoce el sufijo antes de escribir su texto."""
    digest = hashlib.sha256(learner_text.encode("utf-8")).hexdigest()[:12]
    return f"learner_response_{digest}"


def render(request: FeedbackRequest) -> str:
    if request.prompt_version not in _FILES:
        raise ValueError(f"versión de prompt desconocida: {request.prompt_version}")
    common = (HERE / "common_v1.txt").read_text(encoding="utf-8")
    body = (HERE / _FILES[request.prompt_version]).read_text(encoding="utf-8")
    criteria = "\n".join(
        f"- {c.id} ({c.name_es}): "
        + " / ".join(f"{n}: {d}" for n, d in enumerate(c.descriptors_es))
        for c in request.criteria
    )
    tag = boundary(request.learner_text)
    head = common.format(
        task_en=request.task_en,
        objective_es=request.objective_es,
        rubric_id=request.rubric_id,
        rubric_version=request.rubric_version,
        criteria=criteria,
        max_observations=observation_cap(request.kind, request.max_observations),
    ).replace("learner_response", tag)
    body = body.replace("learner_response", tag)
    return head + "\n" + body.replace("{learner_text}", delimit(request.learner_text))
