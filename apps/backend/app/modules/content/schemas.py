"""DTO HTTP de contenido. Los de alumno son listas permitidas: `response_model` descarta
cualquier clave que el servicio no haya puesto a propósito (doble guarda de AC-08)."""

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


class PathDetailOut(PathOut):
    units: list[UnitOut]
    assessments: list[ItemRefOut]


class ContentReportIn(Strict):
    revision_id: uuid.UUID
    activity_id: uuid.UUID | None = None
    attempt_id: uuid.UUID | None = None
    category: Literal["answer_key", "unclear", "audio", "typo", "other"]
    message: str = Field(default="", max_length=1000)
    page: str | None = Field(default=None, max_length=200)


class CreatedOut(BaseModel):
    id: uuid.UUID


# -- admin ------------------------------------------------------------------------------


class RevisionRowOut(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID
    item_slug: str
    item_title: str
    kind: str
    skill: str | None
    form_kind: str | None
    unit: dict[str, Any] | None
    version: int
    status: str
    file_status: str
    content_hash: str
    is_published: bool
    warnings: int
    audio_pending: bool
    open_material_findings: int
    created_at: str


class FindingOut(BaseModel):
    id: uuid.UUID
    author: str
    category: str
    severity: str
    description: str
    status: str
    resolution_note: str | None
    created_at: str
    resolved_at: str | None


class RevisionDetailOut(BaseModel):
    id: uuid.UUID
    item: dict[str, Any]
    version: int
    status: str
    file_status: str
    content_hash: str
    approved_hash: str | None
    approved_at: str | None
    published_at: str | None
    withdrawn_at: str | None
    withdraw_reason: str | None
    source_path: str
    source_commit: str | None
    lint_errors: int
    lint_warnings: list[dict[str, Any]]
    audio_pending: bool
    body: dict[str, Any]
    activities: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    findings: list[FindingOut]
    decisions: list[dict[str, Any]]
    checklist: list[str]
    preview_practice: ItemOut
    preview_assessment: ItemOut
    blockers: dict[str, list[str]]


class FindingIn(Strict):
    category: str = Field(min_length=2, max_length=40)
    severity: Literal["material", "minor"]
    description: str = Field(min_length=3, max_length=2000)


class FindingPatch(Strict):
    status: Literal["open", "resolved", "wont_fix"]
    resolution_note: str | None = Field(default=None, max_length=2000)


class ApproveIn(Strict):
    content_hash: str = Field(min_length=64, max_length=64)
    note: str | None = Field(default=None, max_length=2000)


class PublishIn(Strict):
    note: str | None = Field(default=None, max_length=2000)


class WithdrawIn(Strict):
    reason: str = Field(max_length=2000)


class AdminUnitOut(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    position: int


class PublishedOut(BaseModel):
    revision_id: uuid.UUID
    item_slug: str
    version: int
