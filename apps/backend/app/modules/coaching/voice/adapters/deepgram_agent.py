"""Voice Agent de Deepgram por WebSocket (`wss://agent.deepgram.com/v1/agent/converse`).

Se autentica con `Authorization: Token <DEEPGRAM_API_KEY>` en el handshake, solo desde el
servidor. La misma clase habla con el Deepgram falso de las pruebas (`tests/fakes/
deepgram_agent.py`) por `ws://127.0.0.1`, sin llave (`VOICE_PROVIDER=fake`, nunca en prod).
Conexión en 5 s como máximo; sin reconexión a media sesión.
"""

from __future__ import annotations

import json
from typing import Any

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, InvalidHandshake, InvalidURI

from app.modules.coaching.voice.domain import MAX_FRAME_BYTES
from app.modules.coaching.voice.ports import AgentClosed, AgentConnectFailed, AgentLink

AGENT_URL = "wss://agent.deepgram.com/v1/agent/converse"


class _Link:
    def __init__(self, ws: ClientConnection) -> None:
        self._ws = ws

    async def send_json(self, message: dict[str, Any]) -> None:
        try:
            await self._ws.send(json.dumps(message))
        except ConnectionClosed as exc:
            raise AgentClosed() from exc

    async def send_audio(self, chunk: bytes) -> None:
        try:
            await self._ws.send(chunk)
        except ConnectionClosed as exc:
            raise AgentClosed() from exc

    async def recv(self) -> bytes | dict[str, Any]:
        try:
            message = await self._ws.recv()
        except ConnectionClosed as exc:
            raise AgentClosed() from exc
        if isinstance(message, bytes):
            return message
        try:
            data = json.loads(message)
        except ValueError:
            return {"type": "Unparsable"}
        return data if isinstance(data, dict) else {"type": "Unparsable"}

    async def close(self) -> None:
        await self._ws.close()

    def abort(self) -> None:
        self._ws.transport.abort()


class DeepgramVoiceAgent:
    provider = "deepgram"

    def __init__(self, api_key: str | None, *, model: str, url: str = AGENT_URL) -> None:
        if url == AGENT_URL and not api_key:
            raise ValueError("falta DEEPGRAM_API_KEY")
        self._key = api_key
        self.model = model
        self.url = url

    async def connect(self, timeout_s: float) -> AgentLink:
        headers = {"Authorization": f"Token {self._key}"} if self._key else {}
        try:
            ws = await connect(
                self.url,
                additional_headers=headers,
                open_timeout=timeout_s,
                close_timeout=2,
                max_size=MAX_FRAME_BYTES,
            )
        except (OSError, TimeoutError, InvalidHandshake, InvalidURI) as exc:
            raise AgentConnectFailed(type(exc).__name__) from exc
        return _Link(ws)
