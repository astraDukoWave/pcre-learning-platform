from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bootstrap import Container
from app.cli import main
from app.modules.identity.models import Invitation, UserRole
from tests.helpers import Account


def test_create_admin_invite_prints_link_once(
    container: Container, db: Session, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["create-admin-invite", "--email", "Jefa@Example.com"], container=container) == 0
    out = capsys.readouterr().out
    assert "admin" in out and "/aceptar#t=" in out
    inv = db.scalar(select(Invitation).where(Invitation.email == "jefa@example.com"))
    assert inv is not None and inv.role == UserRole.admin and inv.created_by is None


def test_invite_and_reset_link(
    container: Container, student: Account, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["invite", "--email", "nueva@example.com"], container=container) == 0
    assert "student" in capsys.readouterr().out
    assert main(["reset-link", "--email", student.email], container=container) == 0
    assert "/restablecer#t=" in capsys.readouterr().out
    assert main(["reset-link", "--email", "nadie@example.com"], container=container) == 1
