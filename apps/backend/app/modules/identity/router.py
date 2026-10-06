"""Rutas de identidad. Sin lógica: validan la forma, llaman al servicio y arman la respuesta."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse

from app.http.cookies import SESSION_COOKIE, clear_session_cookie, set_session_cookie
from app.http.deps import AdminDep, AuthDep, ContainerDep, IdentityDep, client_ip
from app.modules.identity.schemas import (
    AcceptInvitationIn,
    AdminInvitationIn,
    AdminUserOut,
    AdminUserPatch,
    DeleteMeIn,
    InvitationInfoOut,
    LinkOut,
    LoginIn,
    MeOut,
    MePatch,
    ResetConfirmIn,
    ResetInfoOut,
    TokenIn,
)
from app.modules.identity.service import IssuedSession, UserView

router = APIRouter(prefix="/api/v1", tags=["identity"])
admin_router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _me(view: UserView, csrf: str) -> MeOut:
    return MeOut(
        id=view.id,
        email=view.email,
        role=view.role,
        display_name=view.display_name,
        timezone=view.timezone,
        goal_purpose=view.goal_purpose,
        target_exam=view.target_exam,
        target_exam_other=view.target_exam_other,
        target_score=view.target_score,
        target_date=view.target_date,
        self_reported_level=view.self_reported_level,
        onboarded=view.onboarded,
        consent_version=view.consent_version,
        csrf_token=csrf,
    )


def _with_session(response: Response, issued: IssuedSession, container: ContainerDep) -> MeOut:
    set_session_cookie(response, issued.token, issued.expires_at, container.clock.now())
    return _me(issued.user, issued.csrf_token)


def _frontend_origin(request: Request, container: ContainerDep) -> str:
    origin = request.headers.get("origin", "").rstrip("/")
    if origin and origin in container.settings.allowed_origins:
        return origin
    return container.settings.app_origin or str(request.base_url).rstrip("/")


@router.post("/auth/invitations/inspect", response_model=InvitationInfoOut)
def inspect_invitation(body: TokenIn, identity: IdentityDep) -> InvitationInfoOut:
    email, expires_at = identity.inspect_invitation(body.token)
    return InvitationInfoOut(
        email=email, consent_version=identity.settings.consent_version, expires_at=expires_at
    )


@router.post("/auth/invitations/accept", response_model=MeOut, status_code=status.HTTP_201_CREATED)
def accept_invitation(
    body: AcceptInvitationIn, response: Response, identity: IdentityDep, container: ContainerDep
) -> MeOut:
    issued = identity.accept_invitation(
        token=body.token,
        password=body.password,
        password_confirm=body.password_confirm,
        accept_privacy=body.accept_privacy,
        consent_version=body.consent_version,
        adult=body.adult,
        display_name=body.display_name,
    )
    return _with_session(response, issued, container)


@router.post("/auth/login", response_model=MeOut)
def login(
    body: LoginIn,
    request: Request,
    response: Response,
    identity: IdentityDep,
    container: ContainerDep,
) -> MeOut:
    issued = identity.login(
        body.email, body.password, client_ip(request), request.cookies.get(SESSION_COOKIE)
    )
    return _with_session(response, issued, container)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(ctx: AuthDep, identity: IdentityDep) -> Response:
    identity.logout(ctx.session_id)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookie(response)
    return response


@router.post("/auth/password-reset/inspect", response_model=ResetInfoOut)
def inspect_reset(body: TokenIn, identity: IdentityDep) -> ResetInfoOut:
    return ResetInfoOut(email=identity.inspect_reset(body.token))


@router.post("/auth/password-reset/confirm", response_model=MeOut)
def confirm_reset(
    body: ResetConfirmIn, response: Response, identity: IdentityDep, container: ContainerDep
) -> MeOut:
    issued = identity.confirm_reset(body.token, body.password, body.password_confirm)
    return _with_session(response, issued, container)


@router.get("/me", response_model=MeOut)
def get_me(ctx: AuthDep, request: Request, identity: IdentityDep) -> MeOut:
    csrf = identity.csrf_for(request.cookies[SESSION_COOKIE])
    return _me(identity.get_me(ctx.user_id), csrf)


@router.patch("/me", response_model=MeOut)
def patch_me(body: MePatch, ctx: AuthDep, request: Request, identity: IdentityDep) -> MeOut:
    view = identity.update_me(ctx.user_id, body.model_dump(exclude_unset=True))
    return _me(view, identity.csrf_for(request.cookies[SESSION_COOKIE]))


@router.get("/me/export")
def export_me(ctx: AuthDep, identity: IdentityDep) -> JSONResponse:
    data: dict[str, Any] = identity.export_me(ctx.user_id)
    return JSONResponse(
        data,
        headers={
            "Content-Disposition": 'attachment; filename="mis-datos-pcre.json"',
            "Cache-Control": "no-store",
        },
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(body: DeleteMeIn, ctx: AuthDep, identity: IdentityDep) -> Response:
    identity.delete_me(ctx.user_id, body.password)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookie(response)
    return response


@admin_router.get("/users", response_model=list[AdminUserOut])
def admin_list_users(_: AdminDep, identity: IdentityDep) -> list[AdminUserOut]:
    return [
        AdminUserOut(
            id=row.user.id,
            email=row.user.email,
            role=row.user.role,
            display_name=row.user.display_name,
            created_at=row.user.created_at,
            last_login_at=row.user.last_login_at,
            is_internal=row.user.is_internal,
            onboarded=row.user.onboarded,
            active_sessions=row.active_sessions,
        )
        for row in identity.list_users()
    ]


@admin_router.post("/invitations", response_model=LinkOut, status_code=status.HTTP_201_CREATED)
def admin_invite(
    body: AdminInvitationIn,
    ctx: AdminDep,
    request: Request,
    identity: IdentityDep,
    container: ContainerDep,
) -> LinkOut:
    link = identity.create_invitation(body.email, created_by=ctx.user_id)
    return LinkOut(
        url=f"{_frontend_origin(request, container)}/aceptar#t={link.token}",
        expires_at=link.expires_at,
    )


@admin_router.post("/users/{user_id}/reset-link", response_model=LinkOut)
def admin_reset_link(
    user_id: uuid.UUID,
    ctx: AdminDep,
    request: Request,
    identity: IdentityDep,
    container: ContainerDep,
) -> LinkOut:
    link = identity.create_reset_link(user_id, created_by=ctx.user_id)
    return LinkOut(
        url=f"{_frontend_origin(request, container)}/restablecer#t={link.token}",
        expires_at=link.expires_at,
    )


@admin_router.post("/users/{user_id}/revoke-sessions", status_code=status.HTTP_204_NO_CONTENT)
def admin_revoke_sessions(user_id: uuid.UUID, _: AdminDep, identity: IdentityDep) -> Response:
    identity.revoke_sessions(user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin_router.patch("/users/{user_id}", response_model=AdminUserOut)
def admin_patch_user(
    user_id: uuid.UUID, body: AdminUserPatch, _: AdminDep, identity: IdentityDep
) -> AdminUserOut:
    view = identity.set_internal(user_id, body.is_internal)
    rows = {r.user.id: r for r in identity.list_users()}
    row = rows[view.id]
    return AdminUserOut(
        id=view.id,
        email=view.email,
        role=view.role,
        display_name=view.display_name,
        created_at=view.created_at,
        last_login_at=view.last_login_at,
        is_internal=view.is_internal,
        onboarded=view.onboarded,
        active_sessions=row.active_sessions,
    )
