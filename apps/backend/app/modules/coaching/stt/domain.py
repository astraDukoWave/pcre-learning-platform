"""Reglas puras de la transcripción (MVP-02 REQ-04).

- Audio `audio/webm` (Opus, Chrome y Firefox) o `audio/mp4` (Safari), de 2 MB y 60 s como
  máximo.
- Repetición: se comparan palabras normalizadas (minúsculas, sin puntuación). Las formas
  contraídas se aceptan si la oración objetivo las declara: «I'm» vale lo mismo que «I am».
  La alineación es la subsecuencia común más larga, así una palabra repetida o de más no
  descuenta las demás. Se cuentan las palabras de la oración objetivo («7 de 9»). El
  resultado no es un acierto ni un error: es una guía (`recognized_ratio`).
- Costo: precio por minuto prorrateado por segundo, redondeado hacia arriba.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

ALLOWED_TYPES = ("audio/webm", "audio/mp4")
MAX_BYTES = 2 * 1024 * 1024
MAX_SECONDS = 60
DURATION_TOLERANCE_S = 0.5
WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
TOKEN = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z]+)?")
CONTRACTIONS = {
    "i'm": "i am",
    "you're": "you are",
    "we're": "we are",
    "they're": "they are",
    "it's": "it is",
    "he's": "he is",
    "she's": "she is",
    "that's": "that is",
    "there's": "there is",
    "i've": "i have",
    "we've": "we have",
    "i'll": "i will",
    "we'll": "we will",
    "i'd": "i would",
    "don't": "do not",
    "doesn't": "does not",
    "didn't": "did not",
    "can't": "cannot",
    "won't": "will not",
    "isn't": "is not",
    "aren't": "are not",
    "wasn't": "was not",
    "let's": "let us",
}


class AudioRejected(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def check_audio(content_type: str, size: int, duration_ms: int) -> str:
    """Devuelve el tipo base aceptado o lanza `AudioRejected` (`audio_type`, `empty`,
    `too_large`, `duration`, `too_long`)."""
    base = content_type.split(";", 1)[0].strip().lower()
    if base not in ALLOWED_TYPES:
        raise AudioRejected("audio_type", "Formato de audio no admitido (usa WebM u MP4).")
    if size <= 0:
        raise AudioRejected("empty", "La grabación está vacía.")
    if size > MAX_BYTES:
        raise AudioRejected("too_large", "La grabación debe pesar menos de 2 MB.")
    if duration_ms <= 0:
        raise AudioRejected("duration", "No pudimos leer la duración de la grabación.")
    if duration_ms > MAX_SECONDS * 1000:
        raise AudioRejected("too_long", "La grabación debe durar 60 segundos o menos.")
    return base


def too_long(duration_s: float) -> bool:
    return duration_s > MAX_SECONDS + DURATION_TOLERANCE_S


def cost_microusd(duration_s: float, price_per_min_microusd: int) -> int:
    """Costo de transcribir `duration_s` segundos (prorrateo por segundo, hacia arriba)."""
    seconds = max(0, math.ceil(duration_s))
    return math.ceil(price_per_min_microusd * seconds / 60)


def max_cost_microusd(price_per_min_microusd: int) -> int:
    """Reserva antes de llamar: el peor caso es el máximo permitido más la tolerancia."""
    return cost_microusd(MAX_SECONDS + DURATION_TOLERANCE_S, price_per_min_microusd)


def _normal(token: str) -> str:
    return token.lower().replace("’", "'").replace("‘", "'")


def words(text: str, *, expand: bool) -> list[str]:
    out: list[str] = []
    for token in WORD.findall(_normal(text)):
        out.extend(CONTRACTIONS.get(token, token).split() if expand else [token])
    return out


@dataclass(frozen=True)
class RepeatResult:
    recognized: int
    total: int
    missing: tuple[str, ...]

    @property
    def ratio(self) -> float:
        return round(self.recognized / self.total, 4) if self.total else 0.0

    def as_dict(self) -> dict[str, object]:
        return {
            "recognized": self.recognized,
            "total": self.total,
            "recognized_ratio": self.ratio,
            "missing": list(self.missing),
        }


def compare_repeat(target: str, transcript: str) -> RepeatResult:
    """Palabras de la oración objetivo que aparecen, en orden, en la transcripción. Una forma
    contraída del objetivo cuenta como una palabra y se reconoce dicha completa o contraída."""
    tokens = TOKEN.findall(target)
    expand = any(_normal(t) in CONTRACTIONS for t in tokens)
    expected: list[str] = []
    owner: list[int] = []
    for index, token in enumerate(tokens):
        for word in words(token, expand=expand):
            expected.append(word)
            owner.append(index)
    matched = _lcs_positions(expected, words(transcript, expand=expand))
    recognized = [
        all(pos in matched for pos, o in enumerate(owner) if o == index)
        for index in range(len(tokens))
    ]
    missing = tuple(t for t, ok in zip(tokens, recognized, strict=True) if not ok)
    return RepeatResult(recognized=sum(recognized), total=len(tokens), missing=missing)


def _lcs_positions(a: list[str], b: list[str]) -> set[int]:
    """Posiciones de `a` que forman la subsecuencia común más larga con `b`."""
    rows, cols = len(a), len(b)
    table = [[0] * (cols + 1) for _ in range(rows + 1)]
    for i in range(rows - 1, -1, -1):
        for j in range(cols - 1, -1, -1):
            table[i][j] = (
                table[i + 1][j + 1] + 1 if a[i] == b[j] else max(table[i + 1][j], table[i][j + 1])
            )
    positions, i, j = set(), 0, 0
    while i < rows and j < cols:
        if a[i] == b[j]:
            positions.add(i)
            i, j = i + 1, j + 1
        elif table[i + 1][j] >= table[i][j + 1]:
            i += 1
        else:
            j += 1
    return positions
