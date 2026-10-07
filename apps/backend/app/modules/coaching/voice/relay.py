"""Relay del coach de voz (ADR-10, MVP-02 REQ-05): navegador ↔ app ↔ Deepgram.

El servidor manda: corta en el deadline, en `stop`, en la desconexión, con un error del
proveedor, con el logout o tras 120 s de silencio; avisa a 30 s del final; manda `KeepAlive`
al proveedor cada 8 s sin audio; aplica 50 frames de audio y 5 mensajes de control por
segundo. La base de datos solo se toca al activar, al comprobar la sesión de la app y al
cerrar, siempre fuera del event loop (`asyncio.to_thread`).

Protocolo con el cliente (JSON; el audio va binario, PCM16 de 16 kHz hacia el servidor y de
24 kHz hacia el cliente):

- Cliente → servidor: `{"type": "stop"}` · `{"type": "aid", "kind": "repeat"|"slower"|"hint"}`.
- Servidor → cliente: `ready` · `transcript` · `user_started_speaking` · `agent_speaking` ·
  `agent_done` · `hint` · `warning` · `error` · `ended` (con `reason` y `duration_s`).
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import math
import time
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any, Protocol

from app.modules.coaching.voice import domain
from app.modules.coaching.voice.ports import (
    AgentClosed,
    AgentConnectFailed,
    AgentLink,
    VoiceAgent,
)
from app.modules.coaching.voice.service import SessionTicket

logger = logging.getLogger("app.coaching.voice")

# Relays vivos de este proceso (un dyno, un worker): `POST /stop` los encuentra aquí.
LIVE: dict[uuid.UUID, VoiceRelay] = {}
# Cierres que siguen aunque se cancele el handler del WebSocket (referencia fuerte).
_CLOSING: set[asyncio.Task[dict[str, Any]]] = set()
# Sesiones con un `POST /stop` que llegó entre la conexión y el arranque del relay.
PENDING_STOP: set[uuid.UUID] = set()


def session_ref(session_id: uuid.UUID) -> str:
    """Hash corto del id de la sesión para los logs (REQ-07)."""
    return hashlib.sha256(str(session_id).encode()).hexdigest()[:12]


class ClientChannel(Protocol):
    async def receive(self) -> bytes | str | None:
        """Un frame del navegador; `None` si se desconectó."""
        ...

    async def send_bytes(self, data: bytes) -> None: ...

    async def send_json(self, data: dict[str, Any]) -> None: ...

    async def close(self, code: int = 1000) -> None: ...


class RelayHooks(Protocol):
    """Operaciones síncronas (base de datos) que el relay corre en un hilo."""

    def mark_active(self, session_id: uuid.UUID) -> datetime | None:
        """Hora de inicio; `None` si la sesión ya no está `reserved` (se detuvo o venció)."""
        ...

    def finish(
        self,
        session_id: uuid.UUID,
        *,
        reason: str,
        transcript: list[dict[str, Any]] | None = None,
        aids: list[dict[str, Any]] | None = None,
        learner_speech_ms: int = 0,
        provider_seconds: float | None = None,
    ) -> dict[str, Any]: ...

    def session_alive(self, auth_session_id: uuid.UUID) -> bool: ...


class VoiceRelay:
    def __init__(
        self,
        ticket: SessionTicket,
        *,
        agent: VoiceAgent,
        agent_settings: dict[str, Any],
        hooks: RelayHooks,
        auth_session_id: uuid.UUID,
        timings: domain.Timings | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        user_ref: str | None = None,
    ) -> None:
        self.ticket = ticket
        # REQ-07: `voice_session_started` lleva el escenario y el `user_ref` (hash salado).
        self.user_ref = user_ref
        self.agent = agent
        self.agent_settings = agent_settings
        self.hooks = hooks
        self.auth_session_id = auth_session_id
        self.t = timings or domain.Timings()
        self.now = monotonic
        self.transcript = domain.Transcript()
        self.aids: list[dict[str, Any]] = []
        self.hints = [str(h) for h in ticket.scenario.get("coach_hints", [])]
        self.hints_used = 0
        self._ended = asyncio.Event()
        self._reason = "disconnect"
        self._client_gone = False
        self._link: AgentLink | None = None
        self._tasks: list[asyncio.Task[None]] = []
        self._closing: asyncio.Task[dict[str, Any]] | None = None
        self._started = 0.0
        self._end_at = 0.0
        self._last_audio = 0.0
        self._last_voice = 0.0
        self._invited = False
        # Voz del alumno: de `UserStartedSpeaking` a su `ConversationText` (REQ-05, ≥ 30 s).
        self.learner_speech_s = 0.0
        self._speaking_since: float | None = None
        # Desde la conexión con el proveedor (cobra por tiempo conectado), en reloj monótono.
        self._provider_since: float | None = None
        self._audio = domain.RateWindow(domain.MAX_AUDIO_FRAMES_PER_S)
        self._control = domain.RateWindow(domain.MAX_CONTROL_PER_S)

    # -- ciclo de vida -------------------------------------------------------------------

    def request_end(self, reason: str) -> None:
        if not self._ended.is_set():
            self._reason = reason
            self._ended.set()

    async def run(self, client: ClientChannel) -> dict[str, Any]:
        LIVE[self.ticket.id] = self
        if self.ticket.id in PENDING_STOP:  # un POST /stop llegó antes que el relay
            PENDING_STOP.discard(self.ticket.id)
            self.request_end("user_stop")
        try:
            return await self._run(client)
        except asyncio.CancelledError:
            # El handler se canceló (cliente perdido o apagado): el cierre con el proveedor
            # y la conciliación siguen en su propia tarea.
            self._client_gone = True
            self._finish_in_background(
                client, self._reason if self._ended.is_set() else "disconnect"
            )
            raise
        except Exception:
            # Un error propio (p. ej. de base de datos al activar): igual se cierra y concilia.
            logger.exception("voice_relay_failed")
            self._finish_in_background(client, "provider_error")
            assert self._closing is not None
            return await asyncio.shield(self._closing)
        finally:
            if self._closing is None:
                LIVE.pop(self.ticket.id, None)

    def _finish_in_background(self, client: ClientChannel, reason: str) -> None:
        if self._closing is None:
            self._closing = asyncio.get_running_loop().create_task(self._close(client, reason))
            # El relay sigue en LIVE hasta que termina de cerrar: un POST /stop lo encuentra.
            self._closing.add_done_callback(lambda _: LIVE.pop(self.ticket.id, None))
        _CLOSING.add(self._closing)
        self._closing.add_done_callback(_CLOSING.discard)

    async def _end(self, client: ClientChannel, reason: str) -> dict[str, Any]:
        self._finish_in_background(client, reason)
        assert self._closing is not None
        return await asyncio.shield(self._closing)

    async def _run(self, client: ClientChannel) -> dict[str, Any]:
        if self._ended.is_set():
            return await self._end(client, self._reason)
        try:
            self._link = await self.agent.connect(self.t.provider_connect_s)
            self._provider_since = self.now()
            await self._link.send_json(self.agent_settings)
            await asyncio.wait_for(self._await_applied(client), self.t.provider_connect_s)
        except (AgentConnectFailed, AgentClosed, TimeoutError) as exc:
            logger.warning("voice_provider_unavailable", extra={"error": type(exc).__name__})
            return await self._end(client, "provider_error")
        if self._ended.is_set():  # se detuvo mientras se conectaba: sin conversación
            return await self._end(client, self._reason)
        started_at = await asyncio.to_thread(self.hooks.mark_active, self.ticket.id)
        if started_at is None:  # la sesión ya se cerró (stop o barrido): sin conversación
            return await self._end(client, self._reason if self._ended.is_set() else "user_stop")
        if self._ended.is_set():  # un stop llegó mientras se activaba: sin `ready`
            return await self._end(client, self._reason)
        self._started = self._last_audio = self._last_voice = self.now()
        remaining = (self.ticket.deadline_at - started_at).total_seconds()
        seconds = max(0.0, min(self.ticket.max_seconds, remaining))
        self._end_at = self._started + seconds
        # El deadline tiene su propio temporizador: no depende de ninguna tarea ni de la base.
        deadline = asyncio.get_running_loop().call_later(seconds, self.request_end, "deadline")
        logger.info(
            "voice_session_started",
            extra={
                "session_ref": session_ref(self.ticket.id),
                "scenario": self.ticket.scenario.get("slug"),
                "user_ref": self.user_ref,
                "seconds": math.ceil(seconds),
            },
        )
        output = self.agent_settings.get("audio", {}).get("output", {})
        await self._safe_send(
            client,
            {
                "type": "ready",
                "seconds": math.ceil(seconds),
                "sample_rate": output.get("sample_rate"),  # PCM16 del coach (REQ-05)
            },
        )
        self._tasks = [
            asyncio.create_task(self._from_client(client)),
            asyncio.create_task(self._from_provider(client)),
            asyncio.create_task(self._tick(client)),
        ]
        for task in self._tasks:
            task.add_done_callback(self._task_done)
        await self._ended.wait()
        deadline.cancel()
        return await self._end(client, self._reason)

    def _task_done(self, task: asyncio.Task[None]) -> None:
        """Una tarea que muere por un error no deja la sesión sin vigilancia: se cierra."""
        if task.cancelled() or task.exception() is None:
            return
        logger.error(
            "voice_relay_task_failed",
            exc_info=(type(task.exception()), task.exception(), None),  # type: ignore[arg-type]
        )
        self.request_end("provider_error")

    async def _alive(self) -> bool:
        """¿Sigue la sesión de la app? Un error transitorio de la base no corta la voz."""
        try:
            return await asyncio.to_thread(self.hooks.session_alive, self.auth_session_id)
        except Exception:
            logger.warning("voice_session_check_failed")
            return True

    async def _await_applied(self, client: ClientChannel) -> None:
        assert self._link is not None
        while True:
            message = await self._link.recv()
            if isinstance(message, dict):
                if message.get("type") == "SettingsApplied":
                    return
                if message.get("type") == "Error":
                    raise AgentClosed()

    async def _close(self, client: ClientChannel, reason: str) -> dict[str, Any]:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        if self._link is not None:
            try:
                await asyncio.wait_for(self._link.close(), self.t.provider_close_s)
            except Exception:
                # Sin respuesta al cierre: se corta el transporte, no se espera al ping.
                with contextlib.suppress(Exception):
                    self._link.abort()
        PENDING_STOP.discard(self.ticket.id)
        try:
            summary = await asyncio.to_thread(
                self.hooks.finish,
                self.ticket.id,
                reason=reason,
                transcript=self.transcript.as_list(),
                aids=self.aids,
                learner_speech_ms=round(self.learner_speech_s * 1000),
                provider_seconds=(
                    self.now() - self._provider_since if self._provider_since is not None else None
                ),
            )
        except Exception:
            # La base falló al cerrar: el barrido concilia la sesión; el alumno igual se entera.
            logger.exception("voice_finish_failed")
            summary = {}
        # Si la sesión ya estaba cerrada (barrido o stop), manda el motivo guardado.
        reason = str(summary.get("end_reason") or reason)
        logger.info(
            "voice_session_ended",
            extra={
                "session_ref": session_ref(self.ticket.id),
                "end_reason": reason,
                "duration_s": summary.get("duration_s"),
                "aids": len(self.aids),
                "turns": len(self.transcript.turns),
            },
        )
        if not self._client_gone:
            await self._safe_send(
                client,
                {"type": "ended", "reason": reason, "duration_s": summary.get("duration_s")},
            )
            with contextlib.suppress(Exception):
                await client.close(1000)
        return summary

    async def _safe_send(self, client: ClientChannel, data: dict[str, Any]) -> None:
        if self._client_gone:
            return
        try:
            await client.send_json(data)
        except Exception:
            self._client_gone = True

    def _elapsed(self) -> float:
        return max(0.0, self.now() - self._started)

    # -- tareas --------------------------------------------------------------------------

    async def _from_client(self, client: ClientChannel) -> None:
        assert self._link is not None
        while not self._ended.is_set():
            frame = await client.receive()
            if frame is None:
                self._client_gone = True
                self.request_end("disconnect")
                return
            if isinstance(frame, bytes):
                if len(frame) > domain.MAX_FRAME_BYTES or not self._audio.allow(self.now()):
                    continue  # frame de más: se descarta
                self._last_audio = self.now()
                try:
                    await self._link.send_audio(frame)
                except AgentClosed:
                    self.request_end("provider_error")
                    return
                continue
            await self._control_message(client, frame)

    async def _control_message(self, client: ClientChannel, raw: str) -> None:
        if not self._control.allow(self.now()):
            await self._safe_send(client, {"type": "error", "code": "rate_limited"})
            return
        if not await self._alive():
            self.request_end("logout")
            return
        try:
            data = json.loads(raw)
        except (ValueError, RecursionError):  # JSON roto o anidado sin fin: `bad_message`
            data = None
        kind = data.get("type") if isinstance(data, dict) else None
        if kind == "stop":
            self.request_end("user_stop")
        elif kind == "aid" and isinstance(data, dict) and data.get("kind") in domain.AID_KINDS:
            await self._aid(client, str(data["kind"]))
        else:
            await self._safe_send(client, {"type": "error", "code": "bad_message"})

    async def _aid(self, client: ClientChannel, kind: str) -> None:
        assert self._link is not None
        entry: dict[str, Any] = {"kind": kind, "at_s": round(self._elapsed(), 1)}
        if kind == "repeat":
            self.transcript.pending_repeats += 1
            await self._link.send_json(
                {"type": "InjectUserMessage", "content": domain.REPEAT_REQUEST}
            )
        elif kind == "slower":
            await self._link.send_json({"type": "UpdatePrompt", "prompt": domain.SLOWER_PROMPT})
        else:
            text = domain.next_hint(self.hints, self.hints_used)
            if text is not None:
                self.hints_used += 1
            entry["text"] = text
            await self._safe_send(client, {"type": "hint", "text": text})
        self.aids.append(entry)

    async def _from_provider(self, client: ClientChannel) -> None:
        assert self._link is not None
        while not self._ended.is_set():
            try:
                message = await self._link.recv()
            except AgentClosed:
                self.request_end("provider_error")
                return
            if isinstance(message, bytes):
                if not self._client_gone:
                    try:
                        await client.send_bytes(message)
                    except Exception:
                        self._client_gone = True
                continue
            kind = message.get("type")
            if kind == "ConversationText":
                turn = self.transcript.add(
                    str(message.get("role")), str(message.get("content", "")), self._elapsed()
                )
                if turn.role == "learner" and not turn.aid:
                    # El eco de «repetir» no es voz del alumno: no cuenta ni reinicia el silencio.
                    if self._speaking_since is not None:
                        self.learner_speech_s += self.now() - self._speaking_since
                    self._speaking_since = None
                    self._learner_spoke()
                await self._safe_send(client, {"type": "transcript", "turn": turn.as_dict()})
            elif kind == "UserStartedSpeaking":
                if self._speaking_since is None:
                    self._speaking_since = self.now()
                self._learner_spoke()
                await self._safe_send(client, {"type": "user_started_speaking"})
            elif kind == "AgentStartedSpeaking":
                await self._safe_send(client, {"type": "agent_speaking"})
            elif kind == "AgentAudioDone":
                await self._safe_send(client, {"type": "agent_done"})
            elif kind == "Error":
                logger.warning(
                    "voice_provider_error",
                    extra={
                        "session_ref": session_ref(self.ticket.id),
                        "code": str(message.get("code")),
                    },
                )
                self.request_end("provider_error")
                return
            elif kind == "InjectionRefused":
                # «Repetir» rechazado (p. ej., mientras el coach habla): sin eco que marcar.
                self.transcript.pending_repeats = max(0, self.transcript.pending_repeats - 1)
                await self._safe_send(client, {"type": "error", "code": "aid_refused"})
            elif kind == "Warning":
                logger.warning("voice_provider_warning", extra={"code": str(message.get("code"))})

    def _learner_spoke(self) -> None:
        self._last_voice = self.now()
        self._invited = False

    async def _tick(self, client: ClientChannel) -> None:
        assert self._link is not None
        warned = False
        last_keepalive = self.now()
        last_auth = self.now()
        while not self._ended.is_set():
            await asyncio.sleep(self.t.tick_s)
            now = self.now()
            if now >= self._end_at:
                self.request_end("deadline")
                return
            if not warned and now >= self._end_at - self.t.warning_before_s:
                warned = True
                await self._safe_send(
                    client, {"type": "warning", "seconds_left": math.ceil(self._end_at - now)}
                )
            quiet = now - self._last_voice
            if quiet >= self.t.silence_end_s:
                self.request_end("silence")
                return
            try:
                if quiet >= self.t.silence_invite_s and not self._invited:
                    self._invited = True
                    await self._link.send_json(
                        {"type": "InjectAgentMessage", "message": domain.SILENCE_INVITE}
                    )
                idle = min(now - self._last_audio, now - last_keepalive)
                if idle >= self.t.keepalive_s:
                    last_keepalive = now
                    await self._link.send_json({"type": "KeepAlive"})
            except AgentClosed:
                self.request_end("provider_error")
                return
            if now - last_auth >= self.t.auth_check_s:
                last_auth = now
                if not await self._alive():
                    self.request_end("logout")
                    return
