"""MVP-02 REQ-05 con el Deepgram falso (servidor `websockets` local): AC-07 (Origin, dueño,
una conexión, 409 y 503 de cupo), AC-08 (deadline del servidor con `VOICE_MAX_SESSION_S=3`),
AC-09 (desconexión y logout), AC-10 (barrido de huérfanas) y AC-11 (ayudas).

El relay toca la base desde otros hilos: estas pruebas usan commits reales
(`committed_container`), con cuentas `@race.example.com` que se borran al final.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from starlette.websockets import WebSocketDisconnect

from app.bootstrap import Container
from app.core.config import Settings
from app.http.cookies import SESSION_COOKIE
from app.main import create_app
from app.modules.coaching.voice import relay as voice_relay
from app.modules.coaching.voice.adapters.deepgram_agent import DeepgramVoiceAgent
from app.modules.coaching.voice.domain import Timings
from app.modules.coaching.voice.models import VoiceSession
from app.modules.content.service_editorial import EditorialService
from app.modules.identity.models import User, UserRole
from app.modules.insights.models import ErrorEvent
from app.modules.usage.models import AiRun, BudgetPeriod
from tests.conftest import TEST_ORIGIN
from tests.content.builder import write_content
from tests.fakes.deepgram_agent import BYTES_PER_LEARNER_TURN, FakeDeepgramAgent
from tests.helpers import create_user, login

VOICE = {
    "voice_enabled": True,
    "budget_global_monthly_microusd": 50_000_000,
    "budget_user_monthly_microusd": 5_000_000,
    "voice_max_minutes_per_user_month": 60,
    "voice_provider": "fake",
}
FAST = Timings(
    keepalive_s=0.4,
    warning_before_s=1.0,
    silence_invite_s=30.0,
    silence_end_s=60.0,
    auth_check_s=0.3,
    provider_connect_s=3.0,
    provider_close_s=1.0,
    tick_s=0.05,
)


@dataclass
class World:
    app: Any
    container: Container
    fake: FakeDeepgramAgent
    scenario_id: str

    def student(self, name: str) -> tuple[TestClient, str, uuid.UUID]:
        email = f"{name}@race.example.com"
        with self.container.uow() as s:
            user_id = create_user(s, self.container, email).id
        client = TestClient(
            self.app, base_url="https://testserver", headers={"Origin": TEST_ORIGIN}
        )
        client.__enter__()
        csrf = login(client, email)
        self.container.login_limiter.reset()
        return client, csrf, user_id


@pytest.fixture
def world(committed_container: Container, tmp_path: Path) -> Iterator[World]:
    with FakeDeepgramAgent() as fake:
        c = committed_container
        c.settings = c.settings.model_copy(update={**VOICE, "voice_agent_url": fake.url})
        c.voice_agent = DeepgramVoiceAgent(None, model="fake-agent", url=fake.url)
        c.ready_providers = frozenset({"voice"})
        c.voice_timings = FAST
        editorial = EditorialService(c.uow, c.clock)
        editorial.import_dir(write_content(tmp_path / "voz"))
        with c.uow() as s:
            admin_id = create_user(s, c, "editor@race.example.com", role=UserRole.admin).id
        scenario_id = ""
        for rev in editorial.list_revisions():
            if rev["item_slug"] == "u1-escenario":
                editorial.approve(
                    uuid.UUID(str(rev["id"])), by=admin_id, content_hash=rev["content_hash"]
                )
                editorial.publish(uuid.UUID(str(rev["id"])), by=admin_id)
                scenario_id = str(rev["item_id"])
        assert scenario_id
        yield World(create_app(c.settings, container=c), c, fake, scenario_id)
        with c.uow() as s:  # las sesiones referencian el contenido: se van con sus usuarios
            s.execute(
                delete(VoiceSession).where(
                    VoiceSession.user_id.in_(
                        select(User.id).where(User.email.like("%@race.example.com"))
                    )
                )
            )


def create(
    client: TestClient,
    csrf: str,
    scenario_id: str,
    *,
    key: str | None = None,
    notice: bool = True,
    save: bool = True,
) -> Any:
    return client.post(
        "/api/v1/voice-sessions",
        json={"scenario_id": scenario_id, "accept_voice_notice": notice, "save_transcript": save},
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": key or str(uuid.uuid4())},
    )


def connect(client: TestClient, session_id: str, origin: str = TEST_ORIGIN) -> Any:
    """Como el navegador: mismo origen y la cookie de sesión (el cliente de pruebas no manda
    una cookie `Secure` a `wss://` por sí solo)."""
    cookie = client.cookies.get(SESSION_COOKIE)
    headers = (
        {"origin": origin, "cookie": f"{SESSION_COOKIE}={cookie}"} if cookie else {"origin": origin}
    )
    return client.websocket_connect(f"/ws/voice/{session_id}", headers=headers)


def wait_closed(session_id: str, container: Container | None = None, timeout: float = 5.0) -> None:
    """Espera a que el relay termine y, si se da el contenedor, a que la sesión quede cerrada
    en la base (el cierre puede seguir en su propia tarea)."""
    end = time.monotonic() + timeout
    while uuid.UUID(session_id) in voice_relay.LIVE and time.monotonic() < end:
        time.sleep(0.02)
    assert uuid.UUID(session_id) not in voice_relay.LIVE
    while container is not None and time.monotonic() < end:
        if session_row(container, session_id).status in ("ended", "failed", "expired"):
            return
        time.sleep(0.02)
    assert container is None, "la sesión no se cerró"


def receive_until(ws: Any, kind: str, limit: int = 40) -> tuple[dict[str, Any], list[Any]]:
    """Lee mensajes (JSON o audio) hasta uno del tipo pedido; devuelve ese y los anteriores."""
    seen: list[Any] = []
    for _ in range(limit):
        message = ws.receive()
        if message.get("bytes") is not None:
            seen.append(message["bytes"])
            continue
        data = json.loads(message["text"])
        if data.get("type") == kind:
            return data, seen
        seen.append(data)
    raise AssertionError(f"no llegó {kind}: {seen}")


def run_of(c: Container, session_id: str) -> AiRun:
    with c.uow() as s:
        session = s.get(VoiceSession, uuid.UUID(session_id))
        assert session is not None and session.ai_run_id is not None
        run = s.get(AiRun, session.ai_run_id)
        assert run is not None
        s.expunge(run)
        return run


def session_row(c: Container, session_id: str) -> VoiceSession:
    with c.uow() as s:
        row = s.get(VoiceSession, uuid.UUID(session_id))
        assert row is not None
        s.expunge(row)
        return row


def test_create_checks_notice_scenario_and_reserves(world: World) -> None:
    client, csrf, user_id = world.student("crea")
    assert create(client, csrf, world.scenario_id, notice=False).json()["error"]["code"] == (
        "voice_notice_required"
    )
    assert create(client, csrf, str(uuid.uuid4())).status_code == 404
    res = create(client, csrf, world.scenario_id)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "reserved" and body["ws_path"] == f"/ws/voice/{body['id']}"
    assert body["max_seconds"] == 300 and body["save_transcript"] is True
    with world.container.uow() as s:
        user = s.get(User, user_id)
        assert user is not None and user.voice_notice_accepted_at is not None
    run = run_of(world.container, body["id"])
    # Reserva del costo máximo: 300 s × USD 0.075/min = 375 000 µUSD; 300 s contra el cupo.
    assert (run.status, run.reserved_microusd, run.observed_units) == ("reserved", 375_000, 300)
    assert run.voice_session_id == uuid.UUID(body["id"])
    assert "key" not in res.text.lower()


def test_same_key_one_live_session_per_learner_and_global_quota(world: World) -> None:
    """AC-07: misma clave → misma sesión; segunda del mismo alumno → 409; cuarta global →
    503 esperado (fuera de `error_events`), con la reserva liberada."""
    client, csrf, _ = world.student("cupo0")
    key = str(uuid.uuid4())
    first = create(client, csrf, world.scenario_id, key=key).json()
    assert create(client, csrf, world.scenario_id, key=key).json()["id"] == first["id"]
    second = create(client, csrf, world.scenario_id)
    assert second.status_code == 409 and second.json()["error"]["code"] == "voice_session_exists"
    for i in (1, 2):
        other, other_csrf, _ = world.student(f"cupo{i}")
        assert create(other, other_csrf, world.scenario_id).status_code == 201
    fourth, fourth_csrf, fourth_id = world.student("cupo3")
    busy = create(fourth, fourth_csrf, world.scenario_id)
    assert busy.status_code == 503 and busy.json()["error"]["code"] == "voice_busy"
    with world.container.uow() as s:
        runs = s.scalars(select(AiRun).where(AiRun.user_id == fourth_id)).all()
        assert [(r.status, r.error_code) for r in runs] == [("failed", "voice_busy")]
        budget = s.scalars(select(BudgetPeriod).where(BudgetPeriod.user_id == fourth_id)).one()
        assert budget.reserved_microusd == 0
        assert s.scalar(select(ErrorEvent).where(ErrorEvent.status_code == 503)) is None


def test_websocket_checks_origin_owner_and_a_single_connection(world: World) -> None:
    client, csrf, _ = world.student("ws")
    session_id = create(client, csrf, world.scenario_id).json()["id"]
    with (
        pytest.raises(WebSocketDisconnect) as foreign,
        connect(client, session_id, origin="https://evil.example.com"),
    ):
        pass
    assert foreign.value.code == 1008  # antes de accept(): uvicorn responde 403
    other, _, _ = world.student("ajena")
    with (
        pytest.raises(WebSocketDisconnect),
        connect(other, session_id),
    ):
        pass
    assert world.fake.connections == []  # nada llegó al proveedor
    with connect(client, session_id) as ws:
        receive_until(ws, "ready")
        with (
            pytest.raises(WebSocketDisconnect),
            connect(client, session_id),
        ):
            pass
        ws.send_json({"type": "stop"})
        ended, _ = receive_until(ws, "ended")
    assert ended["reason"] == "user_stop"
    wait_closed(session_id)
    assert len(world.fake.connections) == 1
    with world.container.uow() as s:  # ni los rechazos ni el cierre son errores del servidor
        assert s.scalar(select(ErrorEvent).where(ErrorEvent.route.like("/ws/%"))) is None


def test_conversation_relays_audio_transcript_and_aids(world: World) -> None:
    """AC-11: las ayudas quedan con su hora; `repeat` y `slower` llegan al proveedor como
    `InjectUserMessage` y `UpdatePrompt`; `hint` lo resuelve el servidor."""
    client, csrf, _ = world.student("conversa")
    session_id = create(client, csrf, world.scenario_id).json()["id"]
    with connect(client, session_id) as ws:
        ready, _ = receive_until(ws, "ready")
        assert ready["seconds"] == 300
        greeting, _ = receive_until(ws, "transcript")
        opening = world.fake.connections[0].received[0]["agent"]["greeting"]
        assert greeting["turn"]["role"] == "coach" and greeting["turn"]["text"] == opening
        _, before = receive_until(ws, "agent_done")
        assert any(isinstance(m, bytes) for m in before)  # audio del coach
        ws.send_bytes(b"\x00\x00" * (BYTES_PER_LEARNER_TURN // 2))
        receive_until(ws, "user_started_speaking")
        learner, _ = receive_until(ws, "transcript")
        assert learner["turn"]["role"] == "learner" and learner["turn"]["aid"] is False
        receive_until(ws, "agent_done")
        ws.send_json({"type": "aid", "kind": "repeat"})
        repeat, _ = receive_until(ws, "transcript")
        assert repeat["turn"]["text"] == "Could you repeat that, please?"
        assert repeat["turn"]["aid"] is True
        receive_until(ws, "agent_done")
        ws.send_json({"type": "aid", "kind": "slower"})
        ws.send_json({"type": "aid", "kind": "hint"})
        hint, _ = receive_until(ws, "hint")
        assert hint["text"] == "Ask about the time first."  # primera pista del escenario
        ws.send_json({"type": "aid", "kind": "magic"})
        bad, _ = receive_until(ws, "error")
        assert bad["code"] == "bad_message"
        ws.send_json({"type": "stop"})
        ended, _ = receive_until(ws, "ended")
    assert ended["reason"] == "user_stop"
    wait_closed(session_id)
    received = world.fake.connections[0].types()
    assert received[0] == "Settings"
    assert "InjectUserMessage" in received and "UpdatePrompt" in received
    settings = world.fake.connections[0].received[0]
    assert settings["agent"]["think"]["prompt"].startswith("You are ")
    assert "authorization" not in world.fake.connections[0].headers  # sin llave con el falso
    row = session_row(world.container, session_id)
    assert row.status == "ended" and row.end_reason == "user_stop"
    assert [a["kind"] for a in row.aids] == ["repeat", "slower", "hint"]
    assert all(isinstance(a["at_s"], float) for a in row.aids)
    assert row.transcript is not None and len(row.transcript) >= 4
    run = run_of(world.container, session_id)
    assert row.ended_at is not None and row.started_at is not None
    seconds = (row.ended_at - row.started_at).total_seconds()
    assert run.status == "succeeded" and run.observed_units is not None
    assert run.observed_units >= int(seconds)
    assert run.cost_microusd == -(-75_000 * run.observed_units // 60)


def test_without_consent_only_duration_and_aids_are_kept(world: World) -> None:
    client, csrf, _ = world.student("sinconsentimiento")
    session_id = create(client, csrf, world.scenario_id, save=False).json()["id"]
    with connect(client, session_id) as ws:
        receive_until(ws, "agent_done")
        ws.send_json({"type": "aid", "kind": "hint"})
        receive_until(ws, "hint")
        ws.send_json({"type": "stop"})
        receive_until(ws, "ended")
    wait_closed(session_id)
    row = session_row(world.container, session_id)
    assert row.transcript is None and row.feedback is None
    assert [a["kind"] for a in row.aids] == ["hint"] and row.ended_at is not None


def test_server_deadline_closes_the_provider_and_settles(world: World) -> None:
    """AC-08: con `VOICE_MAX_SESSION_S=3`, el servidor cierra al proveedor a los 3 s (±0.5),
    avisa antes y el cliente recibe `ended(deadline)`; la reserva se liquida."""
    world.container.settings = world.container.settings.model_copy(
        update={"voice_max_session_s": 3}
    )
    app = create_app(world.container.settings, container=world.container)
    world.app = app
    client, csrf, _ = world.student("deadline")
    body = create(client, csrf, world.scenario_id).json()
    assert body["max_seconds"] == 3
    with connect(client, body["id"]) as ws:
        warning, _ = receive_until(ws, "warning", limit=80)
        assert warning["seconds_left"] <= 1
        ended, _ = receive_until(ws, "ended", limit=80)
    assert ended["reason"] == "deadline"
    wait_closed(body["id"])
    conn = world.fake.connections[0]
    assert conn.applied_at is not None and conn.closed_at is not None
    assert abs((conn.closed_at - conn.applied_at) - 3.0) <= 0.5
    run = run_of(world.container, body["id"])
    assert run.status == "succeeded" and run.observed_units in (3, 4)
    assert run.cost_microusd == -(-75_000 * run.observed_units // 60)
    with world.container.uow() as s:
        budget = s.scalars(select(BudgetPeriod).where(BudgetPeriod.user_id == run.user_id)).one()
        assert budget.reserved_microusd == 0 and budget.spent_microusd == run.cost_microusd


def test_keepalive_is_sent_while_the_learner_is_quiet(world: World) -> None:
    client, csrf, _ = world.student("keepalive")
    session_id = create(client, csrf, world.scenario_id).json()["id"]
    with connect(client, session_id) as ws:
        receive_until(ws, "agent_done")
        time.sleep(1.0)
        ws.send_json({"type": "stop"})
        receive_until(ws, "ended")
    wait_closed(session_id)
    assert world.fake.connections[0].types().count("KeepAlive") >= 1


def test_client_disconnect_closes_the_provider_within_two_seconds(world: World) -> None:
    """AC-09 (desconexión)."""
    client, csrf, _ = world.student("desconecta")
    session_id = create(client, csrf, world.scenario_id).json()["id"]
    with connect(client, session_id) as ws:
        receive_until(ws, "agent_done")
    left = time.monotonic()
    closed = world.fake.wait_closed()
    assert closed is not None and closed - left <= 2.0
    wait_closed(session_id, world.container)
    row = session_row(world.container, session_id)
    assert row.end_reason == "disconnect" and row.status == "ended"


def test_logout_ends_the_session(world: World) -> None:
    """AC-09 (logout en otra pestaña): la sesión de la app se revisa cada 30 s (aquí 0.3 s)."""
    client, csrf, _ = world.student("logout")
    session_id = create(client, csrf, world.scenario_id).json()["id"]
    with connect(client, session_id) as ws:
        receive_until(ws, "agent_done")
        other_tab = TestClient(
            world.app, base_url="https://testserver", headers={"Origin": TEST_ORIGIN}
        )
        other_tab.cookies = client.cookies
        assert other_tab.post(
            "/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}
        ).status_code in (
            200,
            204,
        )
        ended, _ = receive_until(ws, "ended", limit=80)
    assert ended["reason"] == "logout"
    wait_closed(session_id)


def test_silence_invites_then_ends(world: World) -> None:
    world.container.voice_timings = Timings(
        keepalive_s=8.0,
        silence_invite_s=0.5,
        silence_end_s=1.2,
        auth_check_s=30.0,
        provider_connect_s=3.0,
        provider_close_s=1.0,
        tick_s=0.05,
    )
    client, csrf, _ = world.student("silencio")
    session_id = create(client, csrf, world.scenario_id).json()["id"]
    with connect(client, session_id) as ws:
        ended, _ = receive_until(ws, "ended", limit=80)
    assert ended["reason"] == "silence"
    wait_closed(session_id)
    assert "InjectAgentMessage" in world.fake.connections[0].types()


def test_provider_error_suggests_text_mode_and_releases_when_never_started(
    world: World,
) -> None:
    world.fake.reject = True
    client, csrf, _ = world.student("caido")
    session_id = create(client, csrf, world.scenario_id).json()["id"]
    with connect(client, session_id) as ws:
        ended, _ = receive_until(ws, "ended")
    assert ended["reason"] == "provider_error"
    wait_closed(session_id)
    row = session_row(world.container, session_id)
    assert row.status == "failed"
    run = run_of(world.container, session_id)
    assert run.status == "failed" and run.cost_microusd == 0  # nunca empezó: sin costo


def test_stop_without_a_connection_and_reading_a_session(world: World) -> None:
    client, csrf, _ = world.student("detener")
    session_id = create(client, csrf, world.scenario_id).json()["id"]
    other, other_csrf, _ = world.student("mirona")
    assert other.get(f"/api/v1/voice-sessions/{session_id}").status_code == 404
    assert (
        other.post(
            f"/api/v1/voice-sessions/{session_id}/stop", headers={"X-CSRF-Token": other_csrf}
        ).status_code
        == 404
    )
    stopped = client.post(
        f"/api/v1/voice-sessions/{session_id}/stop", headers={"X-CSRF-Token": csrf}
    ).json()
    assert stopped["status"] == "failed" and stopped["end_reason"] == "user_stop"
    assert run_of(world.container, session_id).status == "failed"  # reserva liberada
    assert create(client, csrf, world.scenario_id).status_code == 201  # ya no hay sesión viva


def test_sweep_expires_orphans(world: World) -> None:
    """AC-10: una `active` pasada de su deadline (caída simulada) queda `expired` con la
    reserva completa como gasto; una `reserved` vieja se libera."""
    client, csrf, user_id = world.student("huerfana")
    active_id = create(client, csrf, world.scenario_id).json()["id"]
    other, other_csrf, other_id = world.student("abandonada")
    reserved_id = create(other, other_csrf, world.scenario_id).json()["id"]
    c = world.container
    with c.uow() as s:
        row = s.get(VoiceSession, uuid.UUID(active_id))
        assert row is not None
        past = row.created_at - timedelta(minutes=10)
        row.status, row.started_at, row.created_at = "active", past, past
        row.deadline_at = past + timedelta(seconds=330)
        row = s.get(VoiceSession, uuid.UUID(reserved_id))
        assert row is not None
        row.created_at = row.created_at - timedelta(minutes=3)
    from app.modules.coaching.voice.router import voice_service

    assert voice_service(c).sweep() == 2
    assert session_row(c, active_id).status == "expired"
    assert session_row(c, reserved_id).status == "expired"
    spent = run_of(c, active_id)
    assert spent.status == "unknown" and spent.cost_microusd == 375_000
    assert run_of(c, reserved_id).status == "failed"
    with c.uow() as s:
        mine = s.scalars(select(BudgetPeriod).where(BudgetPeriod.user_id == user_id)).one()
        theirs = s.scalars(select(BudgetPeriod).where(BudgetPeriod.user_id == other_id)).one()
        assert (mine.reserved_microusd, mine.spent_microusd) == (0, 375_000)
        assert (theirs.reserved_microusd, theirs.spent_microusd) == (0, 0)


def test_capability_off_is_an_expected_503(settings: Settings, world: World) -> None:
    world.container.ready_providers = frozenset()
    app = create_app(world.container.settings, container=world.container)
    world.app = app
    client, csrf, _ = world.student("apagado")
    res = create(client, csrf, world.scenario_id)
    assert res.status_code == 503 and res.json()["error"]["code"] == "capability_disabled"


def test_per_second_limits_on_audio_and_control_messages(world: World) -> None:
    client, csrf, _ = world.student("limites")
    session_id = create(client, csrf, world.scenario_id).json()["id"]
    with connect(client, session_id) as ws:
        receive_until(ws, "agent_done")
        for _ in range(80):  # 80 frames de 100 bytes en menos de un segundo
            ws.send_bytes(b"\x00" * 100)
        for _ in range(8):
            ws.send_json({"type": "aid", "kind": "hint"})
        limited, _ = receive_until(ws, "error", limit=80)
        assert limited["code"] == "rate_limited"
        time.sleep(1.1)
        ws.send_json({"type": "stop"})
        receive_until(ws, "ended", limit=80)
    wait_closed(session_id, world.container)
    assert world.fake.connections[0].audio_bytes <= 50 * 100
    assert len(session_row(world.container, session_id).aids) <= 5


class MemoryChannel:
    """Cliente en memoria para manejar el relay sin WebSocket."""

    def __init__(self) -> None:
        self.sent: list[Any] = []
        self.closed = asyncio.Event()

    async def receive(self) -> bytes | str | None:
        await self.closed.wait()
        return None

    async def send_bytes(self, data: bytes) -> None:
        self.sent.append(data)

    async def send_json(self, data: dict[str, Any]) -> None:
        self.sent.append(data)

    async def close(self, code: int = 1000) -> None:
        self.closed.set()


def relay_for(world: World, session_id: str, user_id: uuid.UUID) -> tuple[Any, Any]:
    from app.modules.coaching.voice.relay import VoiceRelay
    from app.modules.coaching.voice.router import voice_service
    from app.modules.coaching.voice.settings_builder import AgentConfig, build_settings

    service = voice_service(world.container)
    ticket = service.claim(uuid.UUID(session_id), user_id)  # lo que hace el WebSocket
    config = AgentConfig("nova-3", "open_ai", "gpt-4o-mini", "aura-2-thalia-en", 24_000)
    relay = VoiceRelay(
        ticket,
        agent=world.container.voice_agent,  # type: ignore[arg-type]
        agent_settings=build_settings(ticket.scenario, config),
        hooks=service,
        auth_session_id=uuid.uuid4(),
        timings=FAST,
    )
    return service, relay


def test_stop_while_the_relay_is_starting_never_converses(world: World) -> None:
    """Verificador F1: un POST /stop entre la conexión (claim) y el arranque del relay no
    libera la reserva mientras el relay conversa: el relay se detiene sin conversar."""
    client, csrf, user_id = world.student("carrera")
    session_id = create(client, csrf, world.scenario_id).json()["id"]
    _, relay = relay_for(world, session_id, user_id)
    stopped = client.post(
        f"/api/v1/voice-sessions/{session_id}/stop", headers={"X-CSRF-Token": csrf}
    ).json()
    assert stopped["status"] == "reserved"  # no la cierra: el relay está arrancando
    assert uuid.UUID(session_id) in voice_relay.PENDING_STOP
    summary = asyncio.run(relay.run(MemoryChannel()))
    assert summary["status"] == "failed" and summary["end_reason"] == "user_stop"
    assert world.fake.connections == []  # nunca habló con el proveedor
    assert run_of(world.container, session_id).status == "failed"  # reserva liberada


def test_a_session_closed_meanwhile_is_not_activated(world: World) -> None:
    client, csrf, user_id = world.student("cerrada")
    session_id = create(client, csrf, world.scenario_id).json()["id"]
    service, relay = relay_for(world, session_id, user_id)
    service.finish(uuid.UUID(session_id), reason="expired")  # el barrido llegó primero
    channel = MemoryChannel()
    asyncio.run(relay.run(channel))
    assert not any(isinstance(m, dict) and m.get("type") == "ready" for m in channel.sent)
    assert world.fake.wait_closed() is not None  # el proveedor se cerró sin conversar
    assert session_row(world.container, session_id).status == "failed"


def test_a_failing_session_check_does_not_stop_the_deadline(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verificador F2: un error de la base al revisar la sesión de la app no mata al relay;
    el deadline tiene su propio temporizador."""
    from app.modules.coaching.voice.service import VoiceService

    def broken(self: Any, auth_session_id: uuid.UUID) -> bool:
        raise RuntimeError("pool agotado")

    monkeypatch.setattr(VoiceService, "session_alive", broken)
    world.container.settings = world.container.settings.model_copy(
        update={"voice_max_session_s": 2}
    )
    world.app = create_app(world.container.settings, container=world.container)
    client, csrf, _ = world.student("checkfalla")
    session_id = create(client, csrf, world.scenario_id).json()["id"]
    with connect(client, session_id) as ws:
        receive_until(ws, "ready")
        ws.send_json({"type": "aid", "kind": "hint"})  # también revisa la sesión
        ended, _ = receive_until(ws, "ended", limit=80)
    assert ended["reason"] == "deadline"
    wait_closed(session_id, world.container)


def test_a_dying_task_or_activation_error_still_closes_and_settles(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verificador F2 y F3: una tarea que muere o un error al activar cierran al proveedor y
    concilian, con `provider_error`."""
    from app.modules.coaching.voice import domain as voice_domain
    from app.modules.coaching.voice.service import VoiceService

    def explode(self: Any, role: str, text: str, at_s: float) -> Any:
        raise RuntimeError("bug")

    monkeypatch.setattr(voice_domain.Transcript, "add", explode)
    client, csrf, _ = world.student("tarea")
    session_id = create(client, csrf, world.scenario_id).json()["id"]
    with connect(client, session_id) as ws:
        ended, _ = receive_until(ws, "ended", limit=80)
    assert ended["reason"] == "provider_error"
    wait_closed(session_id, world.container)
    assert world.fake.connections[-1].closed_at is not None
    assert run_of(world.container, session_id).status == "succeeded"  # empezó: se concilia
    monkeypatch.undo()

    def fail_activation(self: Any, session_id: uuid.UUID) -> Any:
        raise RuntimeError("base caída")

    monkeypatch.setattr(VoiceService, "mark_active", fail_activation)
    other, other_csrf, _ = world.student("activacion")
    second = create(other, other_csrf, world.scenario_id).json()["id"]
    with connect(other, second) as ws:
        ended, _ = receive_until(ws, "ended", limit=80)
    assert ended["reason"] == "provider_error"
    wait_closed(second, world.container)
    assert world.fake.connections[-1].closed_at is not None
    assert run_of(world.container, second).status == "failed"  # nunca empezó: se libera


def test_sweep_releases_reservations_left_without_a_session(world: World) -> None:
    """Verificador F4: una reserva de voz abierta sin sesión (falla entre dos commits)."""
    from app.modules.usage.service import UsageService

    c = world.container
    _, _, user_id = world.student("sinsesion")
    usage = UsageService(c.uow, c.clock, c.settings, c.provider_ready)
    run = usage.reserve(
        user_id,
        purpose="voice_session",
        amount=375_000,
        idempotency_key="perdida",
        provider="deepgram",
        voice_seconds=300,
    )
    with c.uow() as s:
        row = s.get(AiRun, run.run_id)
        assert row is not None
        row.created_at = row.created_at - timedelta(minutes=15)
    from app.modules.coaching.voice.router import voice_service

    assert voice_service(c).sweep() == 1
    with c.uow() as s:
        row = s.get(AiRun, run.run_id)
        assert row is not None and row.status == "failed"
        budget = s.scalars(select(BudgetPeriod).where(BudgetPeriod.user_id == user_id)).one()
        assert budget.reserved_microusd == 0


def test_no_key_reaches_the_browser_or_debug_logs(
    world: World, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC-15 (mensajes) y verificador F6: la llave solo viaja al proveedor."""
    from app.core.logging import configure_logging

    key = "clave-secreta-de-prueba-voz-123"
    world.container.voice_agent = DeepgramVoiceAgent(key, model="fake-agent", url=world.fake.url)
    world.app = create_app(world.container.settings, container=world.container)
    configure_logging("DEBUG")
    try:
        client, csrf, _ = world.student("llave")
        created = create(client, csrf, world.scenario_id)
        seen = [created.text]
        with connect(client, created.json()["id"]) as ws:
            for _ in range(6):
                message = ws.receive()
                seen.append(message.get("text") or "")
            ws.send_json({"type": "stop"})
            _, rest = receive_until(ws, "ended", limit=80)
            seen += [json.dumps(m) for m in rest if isinstance(m, dict)]
        wait_closed(created.json()["id"], world.container)
        seen.append(client.get(f"/api/v1/voice-sessions/{created.json()['id']}").text)
    finally:
        configure_logging("INFO")
    assert world.fake.connections[-1].headers.get("authorization") == f"Token {key}"
    assert all(key not in text for text in seen)
    assert key not in capsys.readouterr().out


def test_log_lines_carry_scenario_and_user_ref_but_never_transcript_text(
    world: World, capsys: pytest.CaptureFixture[str]
) -> None:
    """REQ-07: `voice_session_started` (hash del id, escenario, `user_ref`),
    `voice_session_ended` (motivo, duración, ayudas, turnos) y `ai_run_finished`; nunca texto
    de la transcripción."""
    from app.core.logging import configure_logging
    from tests.fakes.deepgram_agent import LEARNER_LINES

    configure_logging("INFO")  # el handler escribe en el stdout que captura `capsys`
    client, csrf, _ = world.student("bitacora")
    session_id = create(client, csrf, world.scenario_id).json()["id"]
    capsys.readouterr()
    with connect(client, session_id) as ws:
        greeting, _ = receive_until(ws, "transcript")
        receive_until(ws, "agent_done")
        ws.send_bytes(b"\x00\x00" * (BYTES_PER_LEARNER_TURN // 2))
        receive_until(ws, "user_started_speaking")
        receive_until(ws, "transcript")
        ws.send_json({"type": "aid", "kind": "hint"})
        receive_until(ws, "hint")
        ws.send_json({"type": "stop"})
        receive_until(ws, "ended")
    wait_closed(session_id, world.container)
    out = capsys.readouterr().out
    lines = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
    by_msg = {line["msg"]: line for line in lines}
    started = by_msg["voice_session_started"]
    assert started["scenario"] == "u1-escenario" and len(started["user_ref"]) == 12
    assert session_id not in out and started["session_ref"] != session_id
    ended = by_msg["voice_session_ended"]
    assert ended["end_reason"] == "user_stop" and ended["aids"] == 1 and ended["turns"] >= 2
    assert ended["duration_s"] is not None
    finished = [line for line in lines if line["msg"] == "ai_run_finished"]
    assert any(line["purpose"] == "voice_session" for line in finished)
    for text in (greeting["turn"]["text"], *LEARNER_LINES, "Ask about the time first."):
        assert text not in out
