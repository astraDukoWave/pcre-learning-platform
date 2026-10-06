"""Panel editorial (REQ-08): solo `role=admin`. Sin lógica: llama al servicio editorial."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.http.deps import AdminDep, ContainerDep
from app.modules.content.schemas import (
    AdminUnitOut,
    ApproveIn,
    FindingIn,
    FindingOut,
    FindingPatch,
    PublishedOut,
    PublishIn,
    RevisionDetailOut,
    RevisionRowOut,
    WithdrawIn,
)
from app.modules.content.service_editorial import EditorialService

router = APIRouter(prefix="/api/v1/admin/content", tags=["admin-content"])


def get_editorial(container: ContainerDep) -> EditorialService:
    return EditorialService(container.uow, container.clock)


EditorialDep = Annotated[EditorialService, Depends(get_editorial)]


@router.get("/revisions", response_model=list[RevisionRowOut])
def list_revisions(
    _: AdminDep,
    editorial: EditorialDep,
    kind: Annotated[str | None, Query(max_length=20)] = None,
    status: Annotated[str | None, Query(max_length=12)] = None,
    unit_id: uuid.UUID | None = None,
) -> list[RevisionRowOut]:
    rows = editorial.list_revisions(kind=kind, status=status, unit_id=unit_id)
    return [RevisionRowOut.model_validate(r) for r in rows]


@router.get("/units", response_model=list[AdminUnitOut])
def list_units(_: AdminDep, editorial: EditorialDep) -> list[AdminUnitOut]:
    return [AdminUnitOut.model_validate(u) for u in editorial.list_units()]


@router.get("/revisions/{revision_id}", response_model=RevisionDetailOut)
def revision_detail(
    revision_id: uuid.UUID, _: AdminDep, editorial: EditorialDep
) -> RevisionDetailOut:
    return RevisionDetailOut.model_validate(editorial.revision_detail(revision_id))


@router.post("/revisions/{revision_id}/findings", response_model=FindingOut, status_code=201)
def add_finding(
    revision_id: uuid.UUID, body: FindingIn, ctx: AdminDep, editorial: EditorialDep
) -> FindingOut:
    return FindingOut.model_validate(
        editorial.add_finding(
            revision_id,
            by=ctx.user_id,
            category=body.category,
            severity=body.severity,
            description=body.description,
        )
    )


@router.patch("/findings/{finding_id}", response_model=FindingOut)
def update_finding(
    finding_id: uuid.UUID, body: FindingPatch, _: AdminDep, editorial: EditorialDep
) -> FindingOut:
    return FindingOut.model_validate(
        editorial.update_finding(
            finding_id, status=body.status, resolution_note=body.resolution_note
        )
    )


@router.post("/revisions/{revision_id}/approve", response_model=RevisionDetailOut)
def approve(
    revision_id: uuid.UUID, body: ApproveIn, ctx: AdminDep, editorial: EditorialDep
) -> RevisionDetailOut:
    return RevisionDetailOut.model_validate(
        editorial.approve(
            revision_id, by=ctx.user_id, content_hash=body.content_hash, note=body.note
        )
    )


@router.post("/revisions/{revision_id}/publish", response_model=RevisionDetailOut)
def publish(
    revision_id: uuid.UUID, body: PublishIn, ctx: AdminDep, editorial: EditorialDep
) -> RevisionDetailOut:
    return RevisionDetailOut.model_validate(
        editorial.publish(revision_id, by=ctx.user_id, note=body.note)
    )


@router.post("/units/{unit_id}/publish", response_model=list[PublishedOut])
def publish_unit(unit_id: uuid.UUID, ctx: AdminDep, editorial: EditorialDep) -> list[PublishedOut]:
    return [
        PublishedOut(revision_id=p.revision_id, item_slug=p.item_slug, version=p.version)
        for p in editorial.publish_unit(unit_id, by=ctx.user_id)
    ]


@router.post("/revisions/{revision_id}/withdraw", response_model=RevisionDetailOut)
def withdraw(
    revision_id: uuid.UUID, body: WithdrawIn, ctx: AdminDep, editorial: EditorialDep
) -> RevisionDetailOut:
    return RevisionDetailOut.model_validate(
        editorial.withdraw(revision_id, by=ctx.user_id, reason=body.reason)
    )
