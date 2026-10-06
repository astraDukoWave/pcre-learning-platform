"""DTO de `usage` (solo admin)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class CapabilityOut(BaseModel):
    capability: str
    enabled: bool
    reason: str | None


class GlobalBudgetOut(BaseModel):
    configured: bool
    limit_microusd: int
    reserved_microusd: int
    spent_microusd: int
    estimated_microusd: int
    warning: bool


class UserUsageOut(BaseModel):
    user_id: uuid.UUID
    email: str
    calls: int
    voice_sessions: int
    voice_seconds: int
    unknown_runs: int
    limit_microusd: int | None
    reserved_microusd: int
    spent_microusd: int
    estimated_microusd: int


class UsageOverviewOut(BaseModel):
    period: str
    period_note: str
    capabilities: list[CapabilityOut]
    global_budget: GlobalBudgetOut
    user_limit_microusd: int | None
    voice_minutes_per_user: int | None
    calls_by_purpose: dict[str, int]
    users: list[UserUsageOut]
