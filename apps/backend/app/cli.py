"""Comandos de gestión: `python -m app.cli <comando>`.

- `create-admin-invite --email`: invitación de rol admin (solo por CLI, en un one-off
  dyno que ejecuta Jonathan).
- `invite --email`: invitación de alumno.
- `reset-link --email`: enlace de reset de un uso.

Cada comando imprime el enlace una sola vez; no se envía por correo.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence

from app.bootstrap import Container, build_container
from app.core.config import get_settings
from app.core.errors import AppError
from app.http.deps import get_identity
from app.modules.identity.models import UserRole


def _origin(container: Container) -> str:
    return container.settings.app_origin or "http://localhost:5173"


def _invite(container: Container, email: str, role: UserRole) -> str:
    link = get_identity(container).create_invitation(email, created_by=None, role=role)
    return (
        f"Invitación ({role.value}) para {link.email}, vence {link.expires_at.isoformat()}:\n"
        f"{_origin(container)}/aceptar#t={link.token}"
    )


def _reset(container: Container, email: str) -> str:
    link = get_identity(container).reset_link_for_email(email)
    return (
        f"Enlace de reset para {link.email}, vence {link.expires_at.isoformat()}:\n"
        f"{_origin(container)}/restablecer#t={link.token}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("create-admin-invite", "invitación de administrador"),
        ("invite", "invitación de alumno"),
        ("reset-link", "enlace de reset de contraseña"),
    ):
        cmd = sub.add_parser(name, help=help_text)
        cmd.add_argument("--email", required=True)
    return parser


def main(argv: Sequence[str] | None = None, container: Container | None = None) -> int:
    args = build_parser().parse_args(argv)
    container = container or build_container(get_settings())
    handlers: dict[str, Callable[[], str]] = {
        "create-admin-invite": lambda: _invite(container, args.email, UserRole.admin),
        "invite": lambda: _invite(container, args.email, UserRole.student),
        "reset-link": lambda: _reset(container, args.email),
    }
    try:
        print(handlers[args.command]())
    except AppError as exc:
        print(f"error: {exc.message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
