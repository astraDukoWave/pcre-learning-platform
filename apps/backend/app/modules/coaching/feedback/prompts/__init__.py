"""Prompts versionados del evaluador (REQ-02). Cambiar un texto exige una versión nueva: la
versión viaja en `ai_runs.prompt_version` y en el reporte del set de evaluación."""

from __future__ import annotations

from pathlib import Path

from app.modules.coaching.feedback.ports import FeedbackRequest

HERE = Path(__file__).parent
VERSIONS = {"writing": "writing-v1", "interview": "interview-v1", "voice": "voice-v1"}
_FILES = {
    "writing-v1": "writing_v1.txt",
    "interview-v1": "interview_v1.txt",
    "voice-v1": "voice_v1.txt",
}


def delimit(learner_text: str) -> str:
    """El texto del alumno no puede cerrar el delimitador ni abrir otro."""
    return learner_text.replace("<", "‹").replace(">", "›")


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
    head = common.format(
        task_en=request.task_en,
        objective_es=request.objective_es,
        rubric_id=request.rubric_id,
        rubric_version=request.rubric_version,
        criteria=criteria,
        max_observations=request.max_observations,
    )
    return head + "\n" + body.replace("{learner_text}", delimit(request.learner_text))
