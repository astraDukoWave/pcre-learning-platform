"""Esquema ejecutable del contrato curricular §9 (Pydantic) y JSON canónico para el hash.

Los archivos YAML de `content/<ruta>/` se validan contra estos modelos antes de
importarse. `extra="forbid"`: un campo desconocido es un error de lint, no se ignora.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Pool = Literal["practice", "review", "assessment"]
Skill = Literal["reading", "listening", "writing", "speaking"]
FileStatus = Literal["draft", "ready-for-review"]
FormKind = Literal["initial", "checkpoint", "final"]
TaskFamily = Literal[
    "complete_the_words",
    "read_in_daily_life",
    "read_academic_passage",
    "listen_choose_response",
    "listen_conversation",
    "listen_announcement",
    "listen_academic_talk",
    "build_a_sentence",
    "write_an_email",
    "write_academic_discussion",
    "listen_and_repeat",
    "take_an_interview",
    "communicative_transfer",
]

# Familia → formato interno (contrato §3).
FAMILY_FORMATS: dict[str, tuple[str, ...]] = {
    "complete_the_words": ("word_completion",),
    "read_in_daily_life": ("choice",),
    "read_academic_passage": ("choice",),
    "listen_choose_response": ("choice",),
    "listen_conversation": ("choice",),
    "listen_announcement": ("choice",),
    "listen_academic_talk": ("choice",),
    "build_a_sentence": ("sentence_order",),
    "write_an_email": ("short_writing",),
    "write_academic_discussion": ("short_writing",),
    "listen_and_repeat": ("recorded_speaking",),
    "take_an_interview": ("recorded_speaking",),
    "communicative_transfer": ("guided_dialogue",),
}
LISTENING_FAMILIES = frozenset(
    {"listen_choose_response", "listen_conversation", "listen_announcement", "listen_academic_talk"}
)
CLOSED_FORMATS = frozenset({"choice", "word_completion", "sentence_order", "guided_dialogue"})
PRODUCTION_FORMATS = frozenset({"short_writing", "recorded_speaking"})


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


NonEmpty = Annotated[str, Field(min_length=1)]
Key = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,80}$")]


class Stimulus(Strict):
    """Texto, pasaje de la lección o audio. La transcripción es una ayuda servida."""

    text_en: str | None = None
    passage: str | None = None
    audio: str | None = None
    transcript: str | None = None

    @model_validator(mode="after")
    def _one_source(self) -> Stimulus:
        if sum(x is not None for x in (self.text_en, self.passage, self.audio)) != 1:
            raise ValueError("el estímulo lleva exactamente uno de text_en, passage o audio")
        if self.audio is not None and not self.transcript:
            raise ValueError("un estímulo de audio necesita su transcripción")
        return self


class ActivityBase(Strict):
    key: Key
    task_family: TaskFamily
    pool: Pool
    objectives: list[NonEmpty] = Field(min_length=1)
    instructions_es: NonEmpty
    prompt_en: str = ""
    stimulus: Stimulus | None = None
    hints: list[NonEmpty] = Field(default_factory=list, max_length=3)
    support_es: str | None = None
    example: str | None = None
    explanation_es: str | None = None
    sources: list[str] = Field(default_factory=list)


class ChoiceOption(Strict):
    id: Annotated[str, Field(pattern=r"^[a-z0-9]{1,8}$")]
    text: NonEmpty
    why_es: str | None = None


class ChoiceActivity(ActivityBase):
    format: Literal["choice"]
    options: list[ChoiceOption] = Field(min_length=2, max_length=6)
    correct: list[str] = Field(min_length=1)
    multiple: bool = False

    @model_validator(mode="after")
    def _check(self) -> ChoiceActivity:
        ids = [o.id for o in self.options]
        if len(set(ids)) != len(ids):
            raise ValueError("ids de opción repetidos")
        if not set(self.correct) <= set(ids):
            raise ValueError("`correct` apunta a una opción inexistente")
        if not self.multiple and len(self.correct) != 1:
            raise ValueError("una selección simple lleva una sola clave")
        if not self.explanation_es:
            raise ValueError("un ítem de selección necesita explanation_es")
        return self


class Gap(Strict):
    id: Annotated[str, Field(pattern=r"^[a-z0-9]{1,8}$")]
    shown: str
    accepted: list[NonEmpty] = Field(min_length=1)
    case_sensitive: bool = False


class WordCompletionActivity(ActivityBase):
    format: Literal["word_completion"]
    text_en: NonEmpty
    gaps: list[Gap] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> WordCompletionActivity:
        for gap in self.gaps:
            if "{{" + gap.id + "}}" not in self.text_en:
                raise ValueError(f"el hueco {gap.id} no aparece en text_en")
            for answer in gap.accepted:
                if not answer.lower().startswith(gap.shown.lower()):
                    raise ValueError(f"la variante '{answer}' no empieza con '{gap.shown}'")
        if not self.explanation_es:
            raise ValueError("un completado necesita explanation_es")
        return self


class SentenceOrderActivity(ActivityBase):
    format: Literal["sentence_order"]
    tokens: list[NonEmpty] = Field(min_length=3, max_length=14)
    accepted_orders: list[list[NonEmpty]] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> SentenceOrderActivity:
        canonical = sorted(self.tokens)
        for order in self.accepted_orders:
            if sorted(order) != canonical:
                raise ValueError("cada orden aceptado usa exactamente las mismas fichas")
        if self.accepted_orders[0] != self.tokens:
            raise ValueError("el primer orden aceptado es el canónico (`tokens`)")
        if not self.explanation_es:
            raise ValueError("un orden necesita explanation_es")
        return self


class ShortWritingActivity(ActivityBase):
    format: Literal["short_writing"]
    min_words: int = Field(ge=10, le=400)
    max_words: int = Field(ge=20, le=600)
    rubric: NonEmpty
    model_answer: NonEmpty
    model_commentary_es: NonEmpty

    @model_validator(mode="after")
    def _check(self) -> ShortWritingActivity:
        if self.min_words >= self.max_words:
            raise ValueError("min_words debe ser menor que max_words")
        return self


class RecordedSpeakingActivity(ActivityBase):
    format: Literal["recorded_speaking"]
    subtype: Literal["listen_and_repeat", "interview"]
    target_sentence: str | None = None
    audio: str | None = None
    question_en: str | None = None
    prep_seconds: int = Field(default=0, ge=0, le=60)
    response_seconds: int = Field(ge=5, le=120)
    rubric: NonEmpty
    model_answer: NonEmpty
    model_commentary_es: NonEmpty

    @model_validator(mode="after")
    def _check(self) -> RecordedSpeakingActivity:
        if self.subtype == "listen_and_repeat" and not (self.target_sentence and self.audio):
            raise ValueError("listen_and_repeat necesita target_sentence y audio")
        if self.subtype == "interview" and not self.question_en:
            raise ValueError("interview necesita question_en")
        return self


class DialogueOption(Strict):
    id: Annotated[str, Field(pattern=r"^[a-z0-9]{1,8}$")]
    text: NonEmpty
    next: str | None = None
    feedback_es: NonEmpty
    good: bool = True


class DialogueNode(Strict):
    id: Annotated[str, Field(pattern=r"^[a-z0-9_-]{1,24}$")]
    speaker: Literal["agent", "narrator"]
    text_en: NonEmpty
    options: list[DialogueOption] = Field(default_factory=list, max_length=4)


class GuidedDialogueActivity(ActivityBase):
    format: Literal["guided_dialogue"]
    start: str
    nodes: list[DialogueNode] = Field(min_length=2)
    success_paths: list[list[str]] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> GuidedDialogueActivity:
        ids = {n.id for n in self.nodes}
        if self.start not in ids:
            raise ValueError("`start` no es un nodo")
        for node in self.nodes:
            for opt in node.options:
                if opt.next is not None and opt.next not in ids:
                    raise ValueError(f"la opción {node.id}/{opt.id} apunta a un nodo inexistente")
        option_ids = {f"{n.id}.{o.id}" for n in self.nodes for o in n.options}
        for path in self.success_paths:
            if not set(path) <= option_ids:
                raise ValueError("success_paths usa ids `nodo.opción` inexistentes")
        return self


Activity = Annotated[
    ChoiceActivity
    | WordCompletionActivity
    | SentenceOrderActivity
    | ShortWritingActivity
    | RecordedSpeakingActivity
    | GuidedDialogueActivity,
    Field(discriminator="format"),
]


class SourceClaim(Strict):
    source: NonEmpty
    claim: NonEmpty
    scope: NonEmpty
    location: str | None = None


class Rule(Strict):
    text: NonEmpty
    source: str | None = None
    applies_when_not_es: str | None = None


class PcreBlock(Strict):
    pattern: NonEmpty
    concept: NonEmpty
    rules: list[Rule] = Field(min_length=1)
    examples: list[NonEmpty] = Field(min_length=2)


class Passage(Strict):
    id: Annotated[str, Field(pattern=r"^[a-z0-9_-]{1,24}$")]
    title_en: str | None = None
    text_en: NonEmpty


class ItemBase(Strict):
    slug: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{2,80}$")]
    title: NonEmpty
    status: FileStatus = "draft"
    position: int = Field(ge=1, le=99)
    objectives: list[NonEmpty] = Field(min_length=1)
    sources: list[SourceClaim] = Field(default_factory=list)
    activities: list[Activity] = Field(min_length=1)


class LessonFile(ItemBase):
    kind: Literal["lesson"]
    unit: NonEmpty
    skill: Skill
    objective_es: NonEmpty
    pcre: PcreBlock
    application_task_es: NonEmpty
    passages: list[Passage] = Field(default_factory=list)


class ScenarioFile(ItemBase):
    kind: Literal["scenario"]
    unit: NonEmpty
    situation_es: NonEmpty
    situation_en: NonEmpty
    learner_role_en: NonEmpty
    agent_persona_en: NonEmpty
    opening_en: NonEmpty
    required_moves: list[NonEmpty] = Field(min_length=1)
    coach_hints: list[NonEmpty] = Field(default_factory=list)
    max_seconds: int = Field(default=300, ge=60, le=300)
    rubric: NonEmpty


class AssessmentFormFile(ItemBase):
    kind: Literal["assessment_form"]
    form_kind: FormKind
    unit: str | None = None
    duration_minutes: int = Field(ge=5, le=60)
    passages: list[Passage] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> AssessmentFormFile:
        if self.form_kind == "checkpoint" and not self.unit:
            raise ValueError("un checkpoint pertenece a una unidad")
        if self.form_kind != "checkpoint" and self.unit:
            raise ValueError("los formularios de ruta no llevan unidad")
        return self


ItemFile = Annotated[LessonFile | ScenarioFile | AssessmentFormFile, Field(discriminator="kind")]


class UnitEntry(Strict):
    slug: Annotated[str, Field(pattern=r"^u[1-9]-[a-z0-9-]+$")]
    position: int = Field(ge=1, le=20)
    title: NonEmpty
    summary: NonEmpty


class PathFile(Strict):
    code: NonEmpty
    exam_code: NonEmpty
    exam_format_version: NonEmpty
    level_from: NonEmpty
    level_to: NonEmpty
    title: NonEmpty
    label: NonEmpty
    catalog_version: int = Field(ge=1)
    units: list[UnitEntry] = Field(min_length=1)


class Objective(Strict):
    code: Annotated[str, Field(pattern=r"^U[1-8]\.[RLWST](\.[0-9]+)?$")]
    unit: int = Field(ge=1, le=8)
    skill: Literal["reading", "listening", "writing", "speaking", "transfer"]
    description_es: NonEmpty
    cefr_ref_es: NonEmpty
    families: list[TaskFamily] = Field(default_factory=list)


class ObjectivesFile(Strict):
    objectives: list[Objective] = Field(min_length=1)


class Source(Strict):
    id: Annotated[str, Field(pattern=r"^[a-z0-9-]{3,60}$")]
    url: Annotated[str, Field(pattern=r"^https://")]
    title: NonEmpty
    publisher: NonEmpty
    accessed_on: date | None = None
    status: Literal["consulted", "pending"]
    note_es: str | None = None

    @model_validator(mode="after")
    def _check(self) -> Source:
        if self.status == "consulted" and self.accessed_on is None:
            raise ValueError("una fuente consultada lleva accessed_on")
        return self


class SourcesFile(Strict):
    sources: list[Source] = Field(min_length=1)


class RubricLevel(Strict):
    score: int = Field(ge=0, le=3)
    descriptor_es: NonEmpty


class RubricCriterion(Strict):
    id: Annotated[str, Field(pattern=r"^[a-z_]{2,40}$")]
    name_es: NonEmpty
    levels: list[RubricLevel] = Field(min_length=4, max_length=4)
    self_assessed_only: bool = False


class Rubric(Strict):
    id: Annotated[str, Field(pattern=r"^[a-z0-9_-]{2,40}$")]
    version: int = Field(ge=1)
    name_es: NonEmpty
    applies_to: list[TaskFamily] = Field(min_length=1)
    criteria: list[RubricCriterion] = Field(min_length=1)
    note_es: str | None = None


class RubricsFile(Strict):
    rubrics: list[Rubric] = Field(min_length=1)


class ScriptLine(Strict):
    speaker: NonEmpty
    text: NonEmpty
    pause_after_ms: int = Field(default=0, ge=0, le=5000)


class AudioEntry(Strict):
    id: Annotated[str, Field(pattern=r"^[a-z0-9-]{3,80}$")]
    script: list[ScriptLine] = Field(min_length=1)
    voices: dict[str, str] = Field(default_factory=dict)
    file: str | None = None
    sha256: str | None = None
    script_hash: str | None = None
    provider: str | None = None
    model: str | None = None
    generated_at: str | None = None
    reviewed_by: str | None = None
    reviewed_at: date | None = None


class AudioManifest(Strict):
    audio: list[AudioEntry] = Field(default_factory=list)


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def item_payload(item: LessonFile | ScenarioFile | AssessmentFormFile) -> dict[str, Any]:
    """Cuerpo que se guarda y se firma. El estado del archivo no entra al hash: marcar
    `ready-for-review` no crea una revisión nueva."""
    return item.model_dump(mode="json", exclude={"status"}, exclude_none=True)


def content_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode()).hexdigest()


def script_hash(entry: AudioEntry) -> str:
    return hashlib.sha256(
        canonical_json([line.model_dump(mode="json") for line in entry.script]).encode()
    ).hexdigest()
