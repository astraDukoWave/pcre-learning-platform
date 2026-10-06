"""Hallazgos del verificador independiente de CS-04 (PR #6)."""

from __future__ import annotations

import threading
import uuid
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.exc import DBAPIError

from app.bootstrap import Container
from app.core.errors import AppError
from app.modules.content.lint import lint_dir
from app.modules.content.service_editorial import EditorialService
from app.modules.identity.models import UserRole
from tests.content.builder import PATH_SLUG, add_listening, write_content
from tests.helpers import Account, create_user

BASE = "/api/v1/admin/content"


def _approve_publish(admin: Account, slug: str, publish: bool = True) -> dict[str, Any]:
    rows = admin.client.get(f"{BASE}/revisions", params={"status": "draft"}).json()
    rev: dict[str, Any] = next(r for r in rows if r["item_slug"] == slug)
    res = admin.client.post(
        f"{BASE}/revisions/{rev['id']}/approve",
        json={"content_hash": rev["content_hash"]},
        headers=admin.headers(),
    )
    assert res.status_code == 200, res.text
    if publish:
        res = admin.client.post(
            f"{BASE}/revisions/{rev['id']}/publish", json={}, headers=admin.headers()
        )
        assert res.status_code == 200, res.text
    return rev


def test_unapproved_title_never_reaches_the_student(
    admin: Account, student: Account, editorial: EditorialService, imported: Path
) -> None:
    """Hallazgo 1 (bloqueante): el texto visible sale de la revisión publicada."""
    rev = _approve_publish(admin, "u1-l1-lectura")
    file = imported / PATH_SLUG / "units/u1/l1-lectura.yaml"
    data = yaml.safe_load(file.read_text())
    data["title"] = "TITULO SIN APROBAR"
    data["position"] = 9
    file.write_text(yaml.safe_dump(data, allow_unicode=True))
    editorial.import_dir(imported)
    lesson = student.client.get(f"/api/v1/lessons/{rev['item_id']}").json()
    assert lesson["title"] == "Elegir un curso" and lesson["revision_version"] == 1
    path_id = student.client.get("/api/v1/learning-paths").json()[0]["id"]
    path = student.client.get(f"/api/v1/learning-paths/{path_id}").text
    assert "TITULO SIN APROBAR" not in path


def test_audio_that_becomes_unreviewed_blocks_publishing(
    admin: Account, editorial: EditorialService, tmp_path: Path
) -> None:
    """Hallazgo 3: el estado de audio se reevalúa en revisiones aprobadas."""
    root = write_content(tmp_path / "c", lambda f: add_listening(f, reviewed=True))
    editorial.import_dir(root)
    rev = _approve_publish(admin, "u1-l2-escucha", publish=False)
    write_content(tmp_path / "c", lambda f: add_listening(f, reviewed=False))
    editorial.import_dir(root)
    res = admin.client.post(
        f"{BASE}/revisions/{rev['id']}/publish", json={}, headers=admin.headers()
    )
    assert res.status_code == 409 and res.json()["error"]["code"] == "audio_pending"


def _codes(root: Path) -> set[str]:
    ((_, issues),) = lint_dir(root).values()
    return {i.code for i in issues if i.severity == "error"}


def test_markers_in_registry_files_and_spanish_todo(tmp_path: Path) -> None:
    """Hallazgos 4 y 5."""
    ok = write_content(
        tmp_path / "a", lambda f: f["units/u1/l1-lectura.yaml"].update(title="Lee todo el texto")
    )
    assert "forbidden_marker" not in _codes(ok)
    bad = write_content(tmp_path / "b", lambda f: f["path.yaml"].update(title="Ruta TBD"))
    assert "forbidden_marker" in _codes(bad)


def test_lint_knows_column_limits(tmp_path: Path) -> None:
    """Hallazgo 6: un título más largo que la columna es un error de lint, no de release."""
    root = write_content(tmp_path, lambda f: f["units/u1/l1-lectura.yaml"].update(title="x" * 250))
    assert "schema" in _codes(root)


def test_initial_and_final_forms_cannot_share_items(tmp_path: Path) -> None:
    """Hallazgo 7."""

    def mutate(f: dict[str, Any]) -> None:
        base = f["units/u1/checkpoint.yaml"]
        for kind in ("initial", "final"):
            form = {k: v for k, v in base.items() if k != "unit"}
            form.update(slug=f"form-{kind}", form_kind=kind)
            form["activities"] = [
                dict(a, key=a["key"].replace("u1.cp", kind[:3])) for a in base["activities"]
            ]
            f[f"assessments/{kind}.yaml"] = form

    assert "duplicate_across_forms" in _codes(write_content(tmp_path, mutate))


def test_publish_and_withdraw_race_never_deadlocks(
    committed_container: Container, tmp_path: Path
) -> None:
    """Hallazgo 2: publicar la nueva y retirar la vigente a la vez → 200 o 409, nunca 500."""
    c = committed_container
    editorial = EditorialService(c.uow, c.clock)
    root = write_content(tmp_path / "content")
    editorial.import_dir(root)
    with c.uow() as s:
        admin_id = create_user(s, c, "editora@race.example.com", role=UserRole.admin).id

    def latest_draft() -> dict[str, Any]:
        return next(
            r for r in editorial.list_revisions(status="draft") if r["item_slug"] == "u1-l1-lectura"
        )

    first = latest_draft()
    editorial.approve(uuid.UUID(first["id"]), by=admin_id, content_hash=first["content_hash"])
    editorial.publish(uuid.UUID(first["id"]), by=admin_id)
    current = first["id"]
    file = root / PATH_SLUG / "units/u1/l1-lectura.yaml"
    for round_ in range(4):
        data = yaml.safe_load(file.read_text())
        data["title"] = f"Elegir un curso (ronda {round_})"
        file.write_text(yaml.safe_dump(data, allow_unicode=True))
        editorial.import_dir(root)
        new = latest_draft()
        editorial.approve(uuid.UUID(new["id"]), by=admin_id, content_hash=new["content_hash"])
        errors: list[BaseException] = []
        barrier = threading.Barrier(2)

        def run(
            fn: Any, barrier: threading.Barrier = barrier, errors: list[BaseException] = errors
        ) -> None:
            barrier.wait()
            try:
                fn()
            except AppError:
                pass  # 409 válido
            except (DBAPIError, RuntimeError) as exc:
                errors.append(exc)

        threads = [
            threading.Thread(
                target=run, args=(lambda n=new["id"]: editorial.publish(uuid.UUID(n), by=admin_id),)
            ),
            threading.Thread(
                target=run,
                args=(
                    lambda o=current: editorial.withdraw(uuid.UUID(o), by=admin_id, reason="ronda"),
                ),
            ),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        assert not errors, errors
        current = new["id"]
