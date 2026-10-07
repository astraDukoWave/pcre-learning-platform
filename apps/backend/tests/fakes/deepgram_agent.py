"""Deepgram Voice Agent falso: servidor `websockets` local con un guion fijo (MVP-02 CS-05).

Emite `Welcome` al conectar; con `Settings`, `SettingsApplied`, el saludo
(`ConversationText` del asistente), audio binario y `AgentAudioDone`. El primer audio de
un turno del alumno produce `UserStartedSpeaking`; al completar un segundo (32 000 bytes
de linear16 a 16 kHz), el turno del alumno del guion y la respuesta del coach. Responde a
`InjectUserMessage`, `InjectAgentMessage` y `UpdatePrompt`, y registra cada mensaje recibido
y la hora de cierre.

Uso en pruebas: `with FakeDeepgramAgent() as fake:` y `VOICE_AGENT_URL=fake.url`. Uso
independiente (E2E): `python -m tests.fakes.deepgram_agent --port 8765`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed

LEARNER_LINES = (
    "Hi, I'd like some information about the evening English classes, please.",
    "How much does the course cost per month?",
    "Is there space in the Monday group?",
    "What do I need to bring to the first class?",
    "Great, thank you very much. Goodbye.",
)
COACH_LINES = (
    "Sure. We have evening classes on Mondays and Wednesdays.",
    "It's eighty dollars a month.",
    "Yes, there are two places left in the Monday group.",
    "Just bring an ID and a notebook.",
    "You're welcome. See you soon!",
)
BYTES_PER_LEARNER_TURN = 32_000  # 1 s de linear16 a 16 kHz mono
COACH_AUDIO = b"\x00\x01" * 2400  # 0.1 s de linear16 a 24 kHz


@dataclass
class Connection:
    headers: dict[str, str]
    opened_at: float
    received: list[dict[str, Any]] = field(default_factory=list)
    audio_bytes: int = 0
    applied_at: float | None = None
    closed_at: float | None = None

    def types(self) -> list[str]:
        return [str(m.get("type")) for m in self.received]


class FakeDeepgramAgent:
    def __init__(
        self,
        *,
        port: int = 0,
        error_after_settings: bool = False,
        reject: bool = False,
        settings_delay_s: float = 0.0,
    ) -> None:
        self.port = port
        self.error_after_settings = error_after_settings
        self.reject = reject
        self.settings_delay_s = settings_delay_s
        self.connections: list[Connection] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server: Server | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()

    @property
    def url(self) -> str:
        return f"ws://127.0.0.1:{self.port}/v1/agent/converse"

    # -- ciclo de vida -------------------------------------------------------------------

    def __enter__(self) -> FakeDeepgramAgent:
        self._thread = threading.Thread(target=self._run, name="fake-deepgram", daemon=True)
        self._thread.start()
        assert self._ready.wait(5), "el Deepgram falso no arrancó"
        return self

    def __exit__(self, *exc: object) -> None:
        if self._loop and self._server:
            self._loop.call_soon_threadsafe(self._server.close)
        if self._thread:
            self._thread.join(5)

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._loop.run_until_complete(self._serve())

    async def _serve(self) -> None:
        self._server = await serve(self._handle, "127.0.0.1", self.port, process_request=None)
        self.port = self._server.sockets[0].getsockname()[1]
        self._ready.set()
        await self._server.wait_closed()

    def wait_closed(self, index: int = -1, timeout: float = 5.0) -> float | None:
        """Espera a que se cierre la conexión `index` y devuelve su hora (monotónica)."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.connections and self.connections[index].closed_at is not None:
                return self.connections[index].closed_at
            time.sleep(0.02)
        return None

    # -- guion ---------------------------------------------------------------------------

    async def _handle(self, ws: ServerConnection) -> None:
        conn = Connection(
            headers={k.lower(): v for k, v in ws.request.headers.raw_items()} if ws.request else {},
            opened_at=time.monotonic(),
        )
        self.connections.append(conn)
        if self.reject:
            await ws.close(code=1008, reason="unauthorized")
            conn.closed_at = time.monotonic()
            return
        turn = 0
        buffered = 0
        try:
            await ws.send(json.dumps({"type": "Welcome", "request_id": "fake-request"}))
            async for message in ws:
                if isinstance(message, bytes):
                    conn.audio_bytes += len(message)
                    if buffered == 0:  # empieza un turno del alumno
                        await ws.send(json.dumps({"type": "UserStartedSpeaking"}))
                    buffered += len(message)
                    if buffered >= BYTES_PER_LEARNER_TURN:
                        buffered = 0
                        await self._learner_said(ws, LEARNER_LINES[turn % len(LEARNER_LINES)])
                        await self._coach(ws, COACH_LINES[turn % len(COACH_LINES)])
                        turn += 1
                    continue
                data = json.loads(message)
                conn.received.append(data)
                kind = data.get("type")
                if kind == "Settings":
                    if self.settings_delay_s:
                        await asyncio.sleep(self.settings_delay_s)
                    await ws.send(json.dumps({"type": "SettingsApplied"}))
                    conn.applied_at = time.monotonic()
                    if self.error_after_settings:
                        await ws.send(
                            json.dumps(
                                {"type": "Error", "description": "fake failure", "code": "FAKE"}
                            )
                        )
                        continue
                    await self._coach(ws, data["agent"].get("greeting", "Hello."))
                elif kind == "InjectUserMessage":
                    await self._learner_turn(ws, str(data.get("content", "")))
                    await self._coach(ws, "Of course. " + COACH_LINES[max(0, turn - 1)])
                elif kind == "InjectAgentMessage":
                    await self._coach(ws, str(data.get("message", "")))
                elif kind == "UpdatePrompt":
                    await ws.send(json.dumps({"type": "PromptUpdated"}))
        except ConnectionClosed:
            pass
        finally:
            conn.closed_at = time.monotonic()

    async def _learner_turn(self, ws: ServerConnection, text: str) -> None:
        await ws.send(json.dumps({"type": "UserStartedSpeaking"}))
        await self._learner_said(ws, text)

    async def _learner_said(self, ws: ServerConnection, text: str) -> None:
        await ws.send(json.dumps({"type": "ConversationText", "role": "user", "content": text}))

    async def _coach(self, ws: ServerConnection, text: str) -> None:
        await ws.send(json.dumps({"type": "AgentThinking", "content": ""}))
        await ws.send(
            json.dumps({"type": "ConversationText", "role": "assistant", "content": text})
        )
        await ws.send(json.dumps({"type": "AgentStartedSpeaking", "total_latency": 0.1}))
        await ws.send(COACH_AUDIO)
        await ws.send(json.dumps({"type": "AgentAudioDone"}))


def main() -> None:
    parser = argparse.ArgumentParser(description="Deepgram Voice Agent falso")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    fake = FakeDeepgramAgent(port=args.port)
    with fake:
        print(f"Deepgram falso en {fake.url}", flush=True)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
