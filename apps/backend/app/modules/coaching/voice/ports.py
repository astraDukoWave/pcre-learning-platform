"""Puerto del agente de voz (ADR-10): el backend abre la conexión con el proveedor, aplica el
deadline y concilia; la llave nunca llega al navegador."""

from __future__ import annotations

from typing import Any, Protocol


class AgentConnectFailed(Exception):
    """No se pudo abrir la conexión con el proveedor (sin costo)."""


class AgentClosed(Exception):
    """El proveedor cerró la conexión."""


class AgentLink(Protocol):
    async def send_json(self, message: dict[str, Any]) -> None: ...

    async def send_audio(self, chunk: bytes) -> None: ...

    async def recv(self) -> bytes | dict[str, Any]:
        """Audio binario o un mensaje JSON; `AgentClosed` al cerrarse."""
        ...

    async def close(self) -> None: ...


class VoiceAgent(Protocol):
    provider: str
    model: str

    async def connect(self, timeout_s: float) -> AgentLink: ...
