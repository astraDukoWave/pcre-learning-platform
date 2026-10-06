"""Comandos de gestión: `python -m app.cli <comando>`.

- `create-admin-invite --email`: invitación de rol admin (solo por CLI, en un one-off
  dyno que ejecuta Jonathan).
- `invite --email`: invitación de alumno.
- `reset-link --email`: enlace de reset de un uso.
- `content lint --dir [--coverage]`: lint del contenido y `docs/contenido/cobertura.md`.
- `content import --dir`: importa borradores (nunca aprueba ni publica).
- `release`: lo que corre la release phase de Heroku: `alembic upgrade head` y la
  importación de `CONTENT_DIR`. Si algo falla, termina con error y Heroku no promueve.
- `dev-seed`: solo con `APP_ENV` dev o test (se niega en prod). Crea una cuenta admin y una
  alumna de prueba, importa el contenido y aprueba y publica todo lo que no tenga bloqueos
  con el revisor `fixture:dev` (visible en la bitácora del panel).

Los enlaces se imprimen una sola vez; no se envían por correo.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

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


def content_lint(content_dir: Path, coverage: Path | None) -> int:
    from app.modules.content.coverage import render_coverage
    from app.modules.content.lint import lint_dir, summarize

    results = lint_dir(content_dir)
    if not results:
        print(f"error: no hay rutas de contenido en {content_dir}", file=sys.stderr)
        return 1
    total_errors = 0
    for name, (bundle, issues) in results.items():
        errors, warnings = summarize(issues)
        total_errors += errors
        for issue in sorted(issues, key=lambda i: (i.severity != "error", i.file, i.code)):
            print(issue.render())
        print(f"{name}: {errors} errores, {warnings} advertencias, {len(bundle.items)} ítems")
        if coverage is not None and bundle.path is not None and bundle.objectives is not None:
            coverage.parent.mkdir(parents=True, exist_ok=True)
            coverage.write_text(render_coverage(bundle, issues), encoding="utf-8")
            print(f"cobertura escrita en {coverage}")
    return 1 if total_errors else 0


def content_import(container: Container, content_dir: Path) -> int:
    from app.modules.content.importer import ImportAborted
    from app.modules.content.service_editorial import EditorialService

    try:
        results = EditorialService(container.uow, container.clock).import_dir(content_dir)
    except ImportAborted as exc:
        for issue in exc.issues:
            print(issue.render(), file=sys.stderr)
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for result in results:
        print(result.render())
    return 0


def release(container: Container) -> int:
    from alembic import command
    from alembic.config import Config

    from app.core.config import BACKEND_DIR

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")
    return content_import(container, container.settings.content_dir)


FIXTURE_REVIEWER = "fixture:dev"


def dev_seed(container: Container, admin_email: str, student_email: str, password: str) -> int:
    import uuid

    from app.modules.content.service_editorial import EditorialService

    if container.settings.app_env == "prod":
        print("error: dev-seed se niega a correr con APP_ENV=prod", file=sys.stderr)
        return 2
    identity = get_identity(container)
    admin_id = identity.ensure_fixture_user(admin_email, UserRole.admin, password)
    identity.ensure_fixture_user(student_email, UserRole.student, password)
    status = content_import(container, container.settings.content_dir)
    if status != 0:
        return status
    editorial = EditorialService(container.uow, container.clock)
    published = skipped = 0
    for row in editorial.list_revisions(status="draft"):
        rev_id = uuid.UUID(row["id"])
        if row["audio_pending"] or row["open_material_findings"]:
            skipped += 1
            continue
        editorial.approve(
            rev_id, by=admin_id, content_hash=row["content_hash"], note=FIXTURE_REVIEWER
        )
        editorial.publish(rev_id, by=admin_id, note=FIXTURE_REVIEWER)
        published += 1
    print(
        f"dev-seed: admin {admin_email}, alumna {student_email}; "
        f"{published} revisiones publicadas por {FIXTURE_REVIEWER}, {skipped} con bloqueos"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    content = sub.add_parser("content", help="contenido como código")
    content_sub = content.add_subparsers(dest="content_command", required=True)
    lint = content_sub.add_parser("lint", help="lint y cobertura")
    lint.add_argument("--dir", type=Path, required=True)
    lint.add_argument("--coverage", type=Path, default=None)
    imp = content_sub.add_parser("import", help="importa borradores")
    imp.add_argument("--dir", type=Path, required=True)
    sub.add_parser("release", help="migración + importación (release phase)")
    seed = sub.add_parser("dev-seed", help="cuentas y contenido de prueba (dev/test)")
    seed.add_argument("--admin-email", default="admin@example.com")
    seed.add_argument("--student-email", default="alumna@example.com")
    seed.add_argument("--password", default="practica-local-1")
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
    if args.command == "content" and args.content_command == "lint":
        return content_lint(args.dir, args.coverage)
    container = container or build_container(get_settings())
    if args.command == "content":
        return content_import(container, args.dir)
    if args.command == "release":
        return release(container)
    if args.command == "dev-seed":
        return dev_seed(container, args.admin_email, args.student_email, args.password)
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
