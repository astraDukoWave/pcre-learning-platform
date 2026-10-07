"""Rutas de `usage`: consumo y costo por periodo (admin) y capacidades encendidas (alumno).
Sin lógica."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.http.deps import AdminDep, AuthDep, ContainerDep
from app.modules.usage.schemas import LearnerCapabilitiesOut, UsageOverviewOut
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


@router.get("/capabilities", response_model=LearnerCapabilitiesOut)
def learner_capabilities(_: AuthDep, svc: UsageDep) -> LearnerCapabilitiesOut:
    """La interfaz decide si ofrece feedback con IA, transcripción o voz; sin ellas muestra la
    alternativa gratuita. El presupuesto del alumno se comprueba al llamar (503)."""
    return LearnerCapabilitiesOut.model_validate(svc.enabled_capabilities())
