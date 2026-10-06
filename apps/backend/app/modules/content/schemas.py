"""DTO HTTP de contenido (panel editorial y reportes). Los DTO de alumno viven en
`practice/schemas.py`, que compone contenido y progreso."""

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
    preview_practice: dict[str, Any]
    preview_assessment: dict[str, Any]
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
