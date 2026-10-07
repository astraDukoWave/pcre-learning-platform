"""Reglas puras de la sesión de voz (MVP-02 REQ-05).

- Cupo: una sesión viva por alumno (índice único parcial) y `MAX_LIVE_GLOBAL` en total.
- Tiempos: el alumno tiene `CONNECT_GRACE_S` para conectar; la conversación dura
  `max_seconds` desde que el proveedor aplica la configuración y nunca pasa de `deadline_at`
  (creación + máximo + gracia). El servidor corta; el reloj del navegador solo informa.
- Costo: segundos facturables = fin − inicio, hacia arriba, por el precio por minuto.
- Límites por segundo: 50 frames de audio y 5 mensajes de control.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

MAX_LIVE_GLOBAL = 3
CONNECT_GRACE_S = 30
MAX_FRAME_BYTES = 1024 * 1024
MAX_AUDIO_FRAMES_PER_S = 50
MAX_CONTROL_PER_S = 5
ORPHAN_RESERVED_S = 120
ORPHAN_ACTIVE_PAST_DEADLINE_S = 60

EndReason = Literal[
    "deadline", "user_stop", "disconnect", "provider_error", "logout", "silence", "expired"
]
AidKind = Literal["repeat", "slower", "hint"]
AID_KINDS: tuple[AidKind, ...] = ("repeat", "slower", "hint")
REPEAT_REQUEST = "Could you repeat that, please?"
SLOWER_PROMPT = "Speak more slowly and use shorter sentences for the rest of the conversation."
SILENCE_INVITE = (
    "Take your time. Would you like to continue? You can answer whenever you are ready."
)


@dataclass(frozen=True)
class Timings:
    """Tiempos del relay; las pruebas los acortan."""

    keepalive_s: float = 8.0
    warning_before_s: float = 30.0
    silence_invite_s: float = 60.0
    silence_end_s: float = 120.0
    auth_check_s: float = 30.0
    provider_connect_s: float = 5.0
    provider_close_s: float = 2.0
    tick_s: float = 0.25


def session_seconds(scenario_max_s: int, configured_max_s: int) -> int:
    return max(1, min(scenario_max_s, configured_max_s))


def deadline_for(created_at: datetime, max_seconds: int) -> datetime:
    """`deadline_at` que devuelve la creación: ahora + máximo + gracia para conectar."""
    return created_at + timedelta(seconds=max_seconds + CONNECT_GRACE_S)


def connect_by(created_at: datetime) -> datetime:
    return created_at + timedelta(seconds=CONNECT_GRACE_S)


def conversation_end(started_at: datetime, max_seconds: int, deadline_at: datetime) -> datetime:
    """La conversación dura `max_seconds` desde el inicio y nunca pasa de `deadline_at`."""
    return min(started_at + timedelta(seconds=max_seconds), deadline_at)


def billable_seconds(started_at: datetime | None, ended_at: datetime) -> int:
    if started_at is None:
        return 0
    return max(0, math.ceil((ended_at - started_at).total_seconds()))


def cost_microusd(seconds: int, price_per_min_microusd: int) -> int:
    return math.ceil(price_per_min_microusd * max(0, seconds) / 60)


@dataclass
class RateWindow:
    """Ventana deslizante de un segundo: `allow` dice si cabe un evento más."""

    limit: int
    stamps: deque[float] = field(default_factory=deque)

    def allow(self, now: float) -> bool:
        while self.stamps and now - self.stamps[0] >= 1.0:
            self.stamps.popleft()
        if len(self.stamps) >= self.limit:
            return False
        self.stamps.append(now)
        return True


@dataclass(frozen=True)
class Turn:
    n: int
    role: Literal["coach", "learner"]
    text: str
    at_s: float
    aid: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "n": self.n,
            "role": self.role,
            "text": self.text,
            "at_s": self.at_s,
            "aid": self.aid,
        }


@dataclass
class Transcript:
    """Turnos en orden. El eco de cada «repetir» pedido (el texto inyectado) se marca como
    ayuda; con dos pedidos seguidos, sus dos ecos."""

    turns: list[Turn] = field(default_factory=list)
    pending_repeats: int = 0

    def add(self, role: str, text: str, at_s: float) -> Turn:
        who: Literal["coach", "learner"] = "learner" if role == "user" else "coach"
        aid = who == "learner" and self.pending_repeats > 0 and text.strip() == REPEAT_REQUEST
        if aid:
            self.pending_repeats -= 1
        elif who == "learner":
            # El eco no llegó (o se rechazó): un «Could you repeat that?» dicho después por el
            # alumno es suyo.
            self.pending_repeats = 0
        turn = Turn(n=len(self.turns) + 1, role=who, text=text, at_s=round(at_s, 1), aid=aid)
        self.turns.append(turn)
        return turn

    def as_list(self) -> list[dict[str, object]]:
        return [t.as_dict() for t in self.turns]


def next_hint(hints: list[str], used: int) -> str | None:
    return hints[used] if used < len(hints) else None
