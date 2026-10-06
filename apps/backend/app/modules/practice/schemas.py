"""DTO HTTP del alumno: listas permitidas. `response_model` descarta cualquier clave que el
servicio no haya puesto a propósito (doble guarda de AC-08)."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Format = Literal[
    "choice",
    "word_completion",
    "sentence_order",
    "short_writing",
    "recorded_speaking",
    "guided_dialogue",
]
ItemState = Literal["not_started", "in_progress", "completed"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AidOut(BaseModel):
    kind: Literal["hint", "support_es", "transcript", "example"]
    count: int


class StimulusOut(BaseModel):
    text_en: str | None = None
    passage: str | None = None
    audio_url: str | None = None
    has_audio: bool = False


class StudentActivityOut(BaseModel):
    id: uuid.UUID
    key: str
    position: int
    format: Format
    task_family: str
    pool: Literal["practice", "review", "assessment"]
    objectives: list[str]
    instructions_es: str
    prompt_en: str
    stimulus: StimulusOut | None
    data: dict[str, Any]
    aids: list[AidOut]


class UnitRefOut(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    position: int


class PcreRuleOut(BaseModel):
    text: str
    source: str | None = None
    applies_when_not_es: str | None = None


class PcreOut(BaseModel):
    pattern: str
    concept: str
    rules: list[PcreRuleOut]
    examples: list[str]


class PassageOut(BaseModel):
    id: str
    title_en: str | None = None
    text_en: str


class ItemOut(BaseModel):
    id: uuid.UUID
    revision_id: uuid.UUID
    revision_version: int
    kind: Literal["lesson", "scenario", "assessment_form"]
    slug: str
    title: str
    unit: UnitRefOut | None
    objectives: list[str]
    activities: list[StudentActivityOut]
    skill: str | None = None
    objective_es: str | None = None
    pcre: PcreOut | None = None
    application_task_es: str | None = None
    passages: list[PassageOut] = Field(default_factory=list)
    situation_es: str | None = None
    situation_en: str | None = None
    learner_role_en: str | None = None
    opening_en: str | None = None
    required_moves: list[str] = Field(default_factory=list)
    max_seconds: int | None = None
    form_kind: str | None = None
    duration_minutes: int | None = None


class PathOut(BaseModel):
    id: uuid.UUID
    code: str
    title: str
    label: str


class ItemRefOut(BaseModel):
    id: uuid.UUID
    kind: str
    slug: str
    title: str
    position: int
    skill: str | None
    form_kind: str | None


class UnitOut(UnitRefOut):
    items: list[ItemRefOut]


class AttemptSummaryOut(BaseModel):
    id: uuid.UUID
    activity_id: uuid.UUID
    response: dict[str, Any]
    evaluation_status: str
    score: float | None
    correct: bool | None
    result: dict[str, Any]
    aided: bool
    submitted_at: str
    mode: str | None = None


class ProgressOut(BaseModel):
    started_at: str | None
    completed_at: str | None


class LessonOut(ItemOut):
    last_attempts: dict[str, AttemptSummaryOut]
    notice: str | None
    progress: ProgressOut


class ItemStateRefOut(ItemRefOut):
    state: ItemState


class UnitStateOut(UnitRefOut):
    items: list[ItemStateRefOut]


class PathStateOut(PathOut):
    units: list[UnitStateOut]
    assessments: list[ItemStateRefOut]


class AidIn(Strict):
    activity_id: uuid.UUID
    kind: Literal["hint", "support_es", "transcript", "example"]
    index: int = Field(default=0, ge=0, le=5)


class AidContentOut(BaseModel):
    kind: str
    index: int
    content: str
    remaining: int


class AttemptIn(Strict):
    activity_id: uuid.UUID
    response: dict[str, Any]
    revision_of: uuid.UUID | None = None
    audio_plays: int = Field(default=0, ge=0, le=50)


class SelfAssessmentIn(Strict):
    """Marca de 0 a 3 por criterio de la rúbrica, enviada después de ver la rúbrica."""

    scores: dict[str, int] = Field(max_length=12)


class AttemptFeedbackOut(BaseModel):
    explanation: str | None = None
    model_answer: str | None = None
    model_commentary_es: str | None = None
    target_sentence: str | None = None
    rubric: dict[str, Any] | None = None


class AttemptDetailOut(AttemptSummaryOut):
    feedback: AttemptFeedbackOut


class AttemptOut(BaseModel):
    id: uuid.UUID
    activity_id: uuid.UUID
    revision_id: uuid.UUID
    mode: str
    evaluation_status: str
    evaluation_source: str
    score: float | None
    correct: bool | None
    result: dict[str, Any]
    aided: bool
    first_attempt: bool
    submitted_at: str
    feedback: AttemptFeedbackOut
    lesson_completed: bool | None
    review_objectives: list[str]


# -- comprobaciones (REQ-12) ---------------------------------------------------------------


class AssessmentFormRefOut(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    form_kind: Literal["initial", "checkpoint", "final"] | None
    duration_minutes: int | None
    unit: UnitRefOut | None


class RunRefOut(BaseModel):
    id: uuid.UUID
    run_number: int
    status: Literal["in_progress", "submitted"]
    comparable: bool
    started_at: str
    submitted_at: str | None


class AssessmentFormOut(AssessmentFormRefOut):
    label: str
    runs: list[RunRefOut]
    open_run_id: uuid.UUID | None
    can_start: bool


class SavedAnswerOut(BaseModel):
    response: dict[str, Any]
    audio_failed: bool
    saved_at: str


class ObjectiveResultOut(BaseModel):
    code: str
    correct: int
    total: int
    not_evaluable: int


class RunSummaryOut(BaseModel):
    objectives: list[ObjectiveResultOut]
    closed_correct: int
    closed_total: int
    productions_answered: int
    productions_total: int
    not_evaluable_audio: int


class ItemResultOut(BaseModel):
    activity_id: uuid.UUID
    answered: bool
    attempt_id: uuid.UUID | None
    evaluation_status: str | None
    correct: bool | None
    result: dict[str, Any]
    feedback: AttemptFeedbackOut


class AssessmentRunOut(RunRefOut):
    form: AssessmentFormRefOut
    label: str
    passages: list[PassageOut]
    items: list[StudentActivityOut]
    answers: dict[str, SavedAnswerOut]
    summary: RunSummaryOut | None
    results: list[ItemResultOut]


class AnswerIn(Strict):
    response: dict[str, Any] = Field(default_factory=dict)
    audio_failed: bool = False


class AnswerSavedOut(BaseModel):
    activity_id: uuid.UUID
    saved_at: str


class DiagnosticResetOut(BaseModel):
    reset: int


# -- repasos (REQ-14): la actividad la entrega práctica; la elige `progress` --------------


class ReviewItemRefOut(BaseModel):
    id: uuid.UUID
    kind: str
    slug: str
    title: str
    unit: UnitRefOut | None


class ReviewOut(BaseModel):
    objective: str
    due: bool
    stage: int | None
    repeated: bool
    item: ReviewItemRefOut
    activity: StudentActivityOut
    passages: list[PassageOut]


class NextReviewOut(BaseModel):
    review: ReviewOut | None
    remaining_due: int
