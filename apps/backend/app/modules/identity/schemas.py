"""DTO HTTP de identidad. `extra="forbid"`: el cuerpo nunca trae rol, email ni `user_id`."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

GoalPurpose = Literal["work", "studies", "certification", "other", "unknown"]
TargetExam = Literal[
    "toefl_ibt", "ielts_academic", "cambridge_b2_first", "toefl_itp", "other", "unknown"
]
SelfLevel = Literal["A2", "B1", "B2", "unknown"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TokenIn(Strict):
    token: str = Field(min_length=20, max_length=200)


class InvitationInfoOut(BaseModel):
    email: str
    consent_version: str
    expires_at: datetime


class AcceptInvitationIn(Strict):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(max_length=256)
    password_confirm: str = Field(max_length=256)
    accept_privacy: bool
    consent_version: str = Field(max_length=40)
    adult: bool
    display_name: str | None = Field(default=None, max_length=80)


class LoginIn(Strict):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(max_length=256)


class ResetInfoOut(BaseModel):
    email: str


class ResetConfirmIn(Strict):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(max_length=256)
    password_confirm: str = Field(max_length=256)


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    role: Literal["student", "admin"]
    display_name: str | None
    timezone: str
    goal_purpose: GoalPurpose | None
    target_exam: TargetExam | None
    target_exam_other: str | None
    target_score: str | None
    target_date: date | None
    self_reported_level: SelfLevel | None
    onboarded: bool
    consent_version: str | None
    csrf_token: str


class MePatch(Strict):
    """Lista explícita de campos editables por el alumno."""

    display_name: str | None = Field(default=None, max_length=80)
    timezone: str | None = Field(default=None, max_length=64)
    goal_purpose: GoalPurpose | None = None
    target_exam: TargetExam | None = None
    target_exam_other: str | None = Field(default=None, max_length=80)
    target_score: str | None = Field(default=None, max_length=20)
    target_date: date | None = None
    self_reported_level: SelfLevel | None = None
    onboarded: bool | None = None


class DeleteMeIn(Strict):
    password: str = Field(max_length=256)


class AdminUserOut(BaseModel):
    id: uuid.UUID
    email: str
    role: Literal["student", "admin"]
    display_name: str | None
    created_at: datetime
    last_login_at: datetime | None
    is_internal: bool
    onboarded: bool
    active_sessions: int


class AdminInvitationIn(Strict):
    email: str = Field(min_length=3, max_length=255)


class LinkOut(BaseModel):
    url: str
    expires_at: datetime


class AdminUserPatch(Strict):
    is_internal: bool
