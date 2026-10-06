"""Separa cada actividad del archivo en columnas públicas y privadas de `activities`.

Lo público (consigna, estímulo sin transcripción, opciones sin clave) puede llegar al
alumno; lo privado (`solution`, `explanation`, `rubric`) solo después de enviar. Las
ayudas (`hints`, `support_es`, `transcript`, `example`) se sirven por `POST /aids`.
"""

from __future__ import annotations

from typing import Any

from app.modules.content.domain import shuffled_options, shuffled_tokens
from app.modules.content.schema import (
    Activity,
    ChoiceActivity,
    GuidedDialogueActivity,
    RecordedSpeakingActivity,
    Rubric,
    SentenceOrderActivity,
    ShortWritingActivity,
    WordCompletionActivity,
)


def activity_columns(act: Activity, rubrics: dict[str, Rubric]) -> dict[str, Any]:
    stimulus = None
    transcript = None
    if act.stimulus is not None:
        stimulus = act.stimulus.model_dump(mode="json", exclude_none=True, exclude={"transcript"})
        transcript = act.stimulus.transcript
    public: dict[str, Any] | None = None
    solution: dict[str, Any] | None = None
    rubric: dict[str, Any] | None = None

    if isinstance(act, ChoiceActivity):
        public = {
            "options": shuffled_options(
                act.key, [{"id": o.id, "text": o.text} for o in act.options]
            ),
            "multiple": act.multiple,
        }
        solution = {
            "correct": list(act.correct),
            "why": {o.id: o.why_es for o in act.options if o.why_es},
        }
    elif isinstance(act, WordCompletionActivity):
        public = {
            "text_en": act.text_en,
            "gaps": [{"id": g.id, "shown": g.shown} for g in act.gaps],
        }
        solution = {
            "gaps": [
                {"id": g.id, "accepted": list(g.accepted), "case_sensitive": g.case_sensitive}
                for g in act.gaps
            ]
        }
    elif isinstance(act, SentenceOrderActivity):
        public = {"tokens": shuffled_tokens(act.key, list(act.tokens))}
        solution = {"accepted_orders": [list(o) for o in act.accepted_orders]}
    elif isinstance(act, ShortWritingActivity):
        public = {"min_words": act.min_words, "max_words": act.max_words}
        solution = {
            "model_answer": act.model_answer,
            "model_commentary_es": act.model_commentary_es,
        }
        rubric = rubrics[act.rubric].model_dump(mode="json") if act.rubric in rubrics else None
    elif isinstance(act, RecordedSpeakingActivity):
        public = {
            "subtype": act.subtype,
            "audio": act.audio,
            "question_en": act.question_en,
            "prep_seconds": act.prep_seconds,
            "response_seconds": act.response_seconds,
        }
        solution = {
            "model_answer": act.model_answer,
            "model_commentary_es": act.model_commentary_es,
            "target_sentence": act.target_sentence,
        }
        rubric = rubrics[act.rubric].model_dump(mode="json") if act.rubric in rubrics else None
    elif isinstance(act, GuidedDialogueActivity):
        public = {
            "start": act.start,
            "nodes": [
                {
                    "id": n.id,
                    "speaker": n.speaker,
                    "text_en": n.text_en,
                    "options": shuffled_options(
                        f"{act.key}:{n.id}",
                        [{"id": o.id, "text": o.text, "next": o.next} for o in n.options],
                    ),
                }
                for n in act.nodes
            ],
        }
        solution = {
            "options": {
                f"{n.id}.{o.id}": {"feedback_es": o.feedback_es, "good": o.good}
                for n in act.nodes
                for o in n.options
            },
            "success_paths": [list(p) for p in act.success_paths],
        }

    return {
        "activity_key": act.key,
        "format": act.format,
        "task_family": act.task_family,
        "pool": act.pool,
        "objective_codes": list(act.objectives),
        "prompt": {"instructions_es": act.instructions_es, "prompt_en": act.prompt_en},
        "stimulus": stimulus,
        "options": public,
        "hints": list(act.hints),
        "support_es": act.support_es,
        "transcript": transcript,
        "example": act.example,
        "solution": solution,
        "explanation": act.explanation_es,
        "rubric": rubric,
    }
