"""Concurrencia real (commits en PostgreSQL, varios hilos): invitaciones de un uso."""

from __future__ import annotations

import threading
from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from app.bootstrap import Container
from app.main import create_app
from app.modules.identity.models import Invitation
from app.modules.identity.service import IdentityService

ORIGIN = {"Origin": "http://localhost:5173"}


def _service(c: Container) -> IdentityService:
    return IdentityService(c.uow, c.clock, c.settings, c.passwords, c.login_limiter)


def _run_parallel(n: int, fn: Callable[[int], int]) -> list[int]:
    barrier = threading.Barrier(n)
    results: list[int] = [0] * n

    def worker(i: int) -> None:
        barrier.wait()
        results[i] = fn(i)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    return sorted(results)


def _accept_body(token: str, c: Container) -> dict[str, object]:
    return {
        "token": token,
        "password": "una frase segura",
        "password_confirm": "una frase segura",
        "accept_privacy": True,
        "consent_version": c.settings.consent_version,
        "adult": True,
    }


def test_same_invitation_accepted_concurrently_creates_one_user(
    committed_container: Container,
) -> None:
    c = committed_container
    link = _service(c).create_invitation("una@race.example.com", created_by=None)
    app = create_app(c.settings, container=c)
    clients = [TestClient(app, base_url="https://testserver", headers=ORIGIN) for _ in range(4)]
    statuses = _run_parallel(
        4,
        lambda i: (
            clients[i]
            .post("/api/v1/auth/invitations/accept", json=_accept_body(link.token, c))
            .status_code
        ),
    )
    assert statuses == [201, 410, 410, 410]
    with c.uow() as s:
        users = s.execute(
            text("SELECT count(*) FROM users WHERE email = 'una@race.example.com'")
        ).scalar()
    assert users == 1


def test_invitations_for_one_email_never_end_in_500(committed_container: Container) -> None:
    c = committed_container
    service = _service(c)
    links = _run_parallel_links(service, "doble@race.example.com", 3)
    with c.uow() as s:
        valid = s.scalar(
            select(func.count())
            .select_from(Invitation)
            .where(Invitation.email == "doble@race.example.com", Invitation.expires_at > func.now())
        )
    assert valid == 1  # el lock por email deja una sola invitación vigente
    app = create_app(c.settings, container=c)
    clients = [TestClient(app, base_url="https://testserver", headers=ORIGIN) for _ in links]
    statuses = _run_parallel(
        len(links),
        lambda i: (
            clients[i]
            .post("/api/v1/auth/invitations/accept", json=_accept_body(links[i], c))
            .status_code
        ),
    )
    assert statuses.count(201) == 1
    assert set(statuses) <= {201, 410}


def _run_parallel_links(service: IdentityService, email: str, n: int) -> list[str]:
    tokens: list[str] = [""] * n
    barrier = threading.Barrier(n)

    def worker(i: int) -> None:
        barrier.wait()
        tokens[i] = service.create_invitation(email, created_by=None).token

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    return tokens
