"""Rutas del coach de voz: crear, consultar y detener una sesión, y el WebSocket del relay.
Sin lógica: el WebSocket valida `Origin`, la sesión de la app y el dueño antes de
`accept()` (un cierre antes de aceptar es un 403 en el handshake) y delega en el relay."""

from __future__ import annotations

import contextlib
import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, WebSocket
from starlette.concurrency import run_in_threadpool
from starlette.websockets import WebSocketDisconnect

from app.bootstrap import Container
from app.http.cookies import SESSION_COOKIE
from app.http.deps import AuthDep, ContainerDep, get_identity
from app.modules.coaching.voice import relay as voice_relay
from app.modules.coaching.voice.schemas import VoiceSessionIn, VoiceSessionOut
from app.modules.coaching.voice.service import VoiceRejected, VoiceService
from app.modules.coaching.voice.settings_builder import AgentConfig, build_settings
from app.modules.identity.service import IdentityService
from app.modules.practice.service import check_idempotency_key
from app.modules.usage.service import UsageService

router = APIRouter(tags=["voice"])
POLICY_VIOLATION = 1008
logger = logging.getLogger("app.coaching.voice")


def voice_service(container: Container) -> VoiceService:
    return VoiceService(
        container.uow,
        container.clock,
        container.settings,
        UsageService(container.uow, container.clock, container.settings, container.provider_ready),
        IdentityService(
            container.uow,
            container.clock,
            container.settings,
            container.passwords,
            container.login_limiter,
        ),
        agent_model=container.voice_agent.model if container.voice_agent else None,
    )


def get_voice(container: ContainerDep) -> VoiceService:
    return voice_service(container)


VoiceDep = Annotated[VoiceService, Depends(get_voice)]


@router.post("/api/v1/voice-sessions", response_model=VoiceSessionOut, status_code=201)
def create_voice_session(
    body: VoiceSessionIn,
    ctx: AuthDep,
    voice: VoiceDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", max_length=80)],
) -> VoiceSessionOut:
    return VoiceSessionOut.model_validate(
        voice.create(
            ctx.user_id,
            scenario_id=body.scenario_id,
            idempotency_key=check_idempotency_key(idempotency_key),
            accept_voice_notice=body.accept_voice_notice,
            save_transcript=body.save_transcript,
        )
    )


@router.get("/api/v1/voice-sessions/{session_id}", response_model=VoiceSessionOut)
def get_voice_session(session_id: uuid.UUID, ctx: AuthDep, voice: VoiceDep) -> VoiceSessionOut:
    return VoiceSessionOut.model_validate(voice.view(ctx.user_id, session_id))


@router.post("/api/v1/voice-sessions/{session_id}/stop", response_model=VoiceSessionOut)
async def stop_voice_session(
    session_id: uuid.UUID, ctx: AuthDep, voice: VoiceDep
) -> VoiceSessionOut:
    """Detener sin el WebSocket (p. ej., la pestaña perdió la conexión). Corre en el event
    loop para avisar al relay vivo sin cruzar hilos."""
    current = await run_in_threadpool(voice.view, ctx.user_id, session_id)  # ajena → 404
    live = voice_relay.LIVE.get(session_id)
    if live is not None:
        live.request_end("user_stop")
        return VoiceSessionOut.model_validate(current)
    stopped, starting = await run_in_threadpool(voice.stop_unconnected, ctx.user_id, session_id)
    if starting:
        # El WebSocket ya reclamó la sesión y el relay está arrancando: lo detiene al
        # registrarse (o ahora, si se registró mientras tanto). Sin `await` entre estas
        # líneas, el event loop no deja que se crucen.
        voice_relay.PENDING_STOP.add(session_id)
        live = voice_relay.LIVE.get(session_id)
        if live is not None:
            voice_relay.PENDING_STOP.discard(session_id)
            live.request_end("user_stop")
    return VoiceSessionOut.model_validate(stopped)


class _Channel:
    def __init__(self, ws: WebSocket) -> None:
        self.ws = ws

    async def receive(self) -> bytes | str | None:
        try:
            message = await self.ws.receive()
        except (WebSocketDisconnect, RuntimeError):
            return None
        if message["type"] == "websocket.disconnect":
            return None
        if message.get("bytes") is not None:
            return bytes(message["bytes"])
        return str(message.get("text") or "")

    async def send_bytes(self, data: bytes) -> None:
        await self.ws.send_bytes(data)

    async def send_json(self, data: dict[str, Any]) -> None:
        await self.ws.send_json(data)

    async def close(self, code: int = 1000) -> None:
        await self.ws.close(code)


@router.websocket("/ws/voice/{session_id}")
async def voice_socket(websocket: WebSocket, session_id: uuid.UUID) -> None:
    container: Container = websocket.app.state.container
    settings = container.settings
    origin = (websocket.headers.get("origin") or "").rstrip("/")
    if origin not in settings.allowed_origins:
        return await _reject(websocket, "origin")  # antes de accept(): 403
    token = websocket.cookies.get(SESSION_COOKIE)
    identity = get_identity(container)
    ctx = await run_in_threadpool(identity.authenticate, token) if token else None
    agent = container.voice_agent
    if agent is None or not settings.voice_enabled:  # apagado o rollback (G5)
        return await _reject(websocket, "voice_off")
    if ctx is None:
        return await _reject(websocket, "no_session")
    voice = voice_service(container)
    try:
        ticket = await run_in_threadpool(voice.claim, session_id, ctx.user_id)
    except VoiceRejected as exc:
        return await _reject(websocket, exc.reason)
    relay: voice_relay.VoiceRelay | None = None
    try:
        await websocket.accept()
        config = AgentConfig(
            listen_model=settings.voice_listen_model,
            think_provider=settings.voice_think_provider,
            think_model=settings.voice_think_model,
            speak_model=settings.voice_speak_model,
            output_sample_rate=settings.voice_output_sample_rate,
        )
        relay = voice_relay.VoiceRelay(
            ticket,
            agent=agent,
            agent_settings=build_settings(ticket.scenario, config),
            hooks=voice,
            auth_session_id=ctx.session_id,
            timings=container.voice_timings,
        )
        await relay.run(_Channel(websocket))
    finally:
        if relay is None:
            # Reclamada pero el relay nunca arrancó: se cierra y se libera aquí.
            voice_relay.PENDING_STOP.discard(session_id)
            with contextlib.suppress(Exception):
                await run_in_threadpool(voice.finish, session_id, reason="disconnect")


async def _reject(websocket: WebSocket, reason: str) -> None:
    logger.info("voice_ws_rejected", extra={"reason": reason})
    await websocket.close(POLICY_VIOLATION)
