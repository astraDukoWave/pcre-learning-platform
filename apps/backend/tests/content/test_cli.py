from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.bootstrap import Container
from app.cli import main
from app.modules.content.models import ContentRevision
from tests.content.builder import write_content


def test_content_lint_writes_coverage_and_fails_on_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = write_content(tmp_path / "ok")
    out = tmp_path / "cobertura.md"
    assert main(["content", "lint", "--dir", str(root), "--coverage", str(out)]) == 0
    assert out.read_text().startswith("# Cobertura de contenido")
    bad = write_content(
        tmp_path / "bad", lambda f: f["units/u1/l1-lectura.yaml"].update(title="x TBD")
    )
    assert main(["content", "lint", "--dir", str(bad)]) == 1
    assert "forbidden_marker" in capsys.readouterr().out


def test_content_import_is_idempotent(tmp_path: Path, container: Container, db: Session) -> None:
    root = write_content(tmp_path / "c")
    assert main(["content", "import", "--dir", str(root)], container=container) == 0
    first = db.scalar(select(func.count()).select_from(ContentRevision))
    assert main(["content", "import", "--dir", str(root)], container=container) == 0
    assert db.scalar(select(func.count()).select_from(ContentRevision)) == first


def test_release_migrates_and_imports_repo_content(container: Container) -> None:
    assert main(["release"], container=container) == 0


def test_dev_seed_publishes_with_fixture_reviewer(
    container: Container, db: Session, capsys: pytest.CaptureFixture[str]
) -> None:
    from app.modules.content.models import EditorialDecision

    assert main(["dev-seed"], container=container) == 0
    assert "fixture:dev" in capsys.readouterr().out
    notes = set(db.scalars(select(EditorialDecision.note)))
    assert notes == {"fixture:dev"}
    published = db.scalar(
        select(func.count())
        .select_from(ContentRevision)
        .where(ContentRevision.status == "published")
    )
    assert published and published >= 1


def test_dev_seed_refuses_prod(container: Container) -> None:
    prod = container.settings.model_copy(
        update={"app_env": "prod", "app_origin": "https://x.example.com"}
    )
    container.settings = prod
    assert main(["dev-seed"], container=container) == 2
