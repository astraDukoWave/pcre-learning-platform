"""Plazo total para llamadas bloqueantes a proveedores externos (`docs/arquitectura.md` §8).

Los timeouts de httpx son por fase y por lectura: una respuesta que llega en trozos lentos
puede pasar de 20 s sin que ninguno se dispare. `call_with_deadline` corre la llamada en un
hilo y deja de esperarla al vencer el plazo; los timeouts de httpx siguen acotando el hilo.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="provider-call")


class DeadlineExceeded(Exception):
    """Venció el plazo. `started` dice si la llamada llegó a empezar (se pudo haber enviado)."""

    def __init__(self, *, started: bool) -> None:
        super().__init__("deadline_exceeded")
        self.started = started


def call_with_deadline[T](fn: Callable[[], T], timeout_s: float) -> T:
    future = _POOL.submit(fn)
    try:
        return future.result(timeout=timeout_s)
    except FutureTimeout:
        # Si la llamada seguía en cola, se cancela: nunca se envió.
        raise DeadlineExceeded(started=not future.cancel()) from None
