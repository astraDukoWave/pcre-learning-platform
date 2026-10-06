"""NFR-06: ninguna prueba puede abrir un socket hacia un proveedor."""

from __future__ import annotations

import socket

import pytest
from pytest_socket import SocketConnectBlockedError


@pytest.mark.filterwarnings("ignore::UserWarning")
@pytest.mark.parametrize("address", [("203.0.113.10", 443), ("198.51.100.7", 80)])
def test_external_connections_are_blocked(address: tuple[str, int]) -> None:
    with pytest.raises(SocketConnectBlockedError):
        socket.create_connection(address, timeout=1)


def test_localhost_is_allowed(engine: object) -> None:
    # La fixture `engine` ya abrió conexiones a PostgreSQL en 127.0.0.1.
    assert engine is not None
