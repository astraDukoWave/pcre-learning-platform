"""Rutas de `usage`: consumo y costo por periodo (solo admin). Sin lógica."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.http.deps import AdminDep, ContainerDep
from app.modules.usage.schemas import UsageOverviewOut
from app.modules.usage.service import UsageService

router = APIRouter(prefix="/api/v1", tags=["usage"])


def get_usage(container: ContainerDep) -> UsageService:
    return UsageService(
        container.uow, container.clock, container.settings, container.provider_ready
    )


UsageDep = Annotated[UsageService, Depends(get_usage)]


@router.get("/admin/usage", response_model=UsageOverviewOut)
def usage_overview(
    _: AdminDep,
    svc: UsageDep,
    period: Annotated[str | None, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")] = None,
) -> UsageOverviewOut:
    return UsageOverviewOut.model_validate(svc.overview(period))
