"""Fixtures y utilidades compartidas: cuentas de prueba y sesiones."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.bootstrap import Container
from app.modules.identity.models import User, UserRole

PASSWORD = "correct horse battery"


@dataclass
class Account:
    id: uuid.UUID
    email: str
    password: str
    client: TestClient
    csrf: str

    def headers(self) -> dict[str, str]:
        return {"X-CSRF-Token": self.csrf}

    def post(self, url: str, **kwargs: object) -> object:
        return self.client.post(url, headers=self.headers(), **kwargs)  # type: ignore[arg-type]


def create_user(
    db: Session,
    container: Container,
    email: str,
    *,
    role: UserRole = UserRole.student,
    password: str = PASSWORD,
    is_internal: bool = False,
) -> User:
    now = container.clock.now()
    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=container.passwords.hash(password),
        role=role,
        consent_version=container.settings.consent_version,
        consent_accepted_at=now,
        adult_attested_at=now,
        is_internal=is_internal,
    )
    db.add(user)
    db.commit()
    return user


def login(client: TestClient, email: str, password: str = PASSWORD) -> str:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return str(res.json()["csrf_token"])


AccountFactory = Callable[..., Account]


@pytest.fixture
def make_account(db: Session, container: Container, app: object) -> AccountFactory:
    """Crea un usuario y un TestClient propio con sesión iniciada (cookies separadas)."""
    clients: list[TestClient] = []

    def factory(
        email: str | None = None,
        *,
        role: UserRole = UserRole.student,
        is_internal: bool = False,
    ) -> Account:
        email = email or f"alumna-{uuid.uuid4().hex[:8]}@example.com"
        user = create_user(db, container, email, role=role, is_internal=is_internal)
        client = TestClient(
            app,  # type: ignore[arg-type]
            base_url="https://testserver",
            headers={"Origin": "http://localhost:5173"},
        )
        clients.append(client)
        csrf = login(client, email)
        container.login_limiter.reset()
        return Account(id=user.id, email=email, password=PASSWORD, client=client, csrf=csrf)

    return factory


@pytest.fixture
def admin(make_account: AccountFactory) -> Account:
    return make_account("admin@example.com", role=UserRole.admin)


@pytest.fixture
def student(make_account: AccountFactory) -> Account:
    return make_account("alumna@example.com")
