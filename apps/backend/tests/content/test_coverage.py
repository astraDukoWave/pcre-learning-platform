from __future__ import annotations

from pathlib import Path

from app.core.config import REPO_DIR
from app.modules.content.coverage import render_coverage
from app.modules.content.lint import lint_dir
from tests.content.builder import write_content


def test_coverage_is_deterministic_and_marks_pending(tmp_path: Path) -> None:
    root = write_content(tmp_path)
    ((bundle, issues),) = lint_dir(root).values()
    first = render_coverage(bundle, issues)
    second = render_coverage(*next(iter(lint_dir(root).values())))
    assert first == second
    assert "`u1.l1.p1`" in first
    assert "| `listen_announcement` | choice | pendiente | pendiente | pendiente |" in first
    assert "Lecciones: 2 de 8" in first
    assert "Ruta: diagnóstico inicial" in first


def test_repo_coverage_file_is_up_to_date() -> None:
    ((bundle, issues),) = lint_dir(REPO_DIR / "content").values()
    expected = render_coverage(bundle, issues)
    assert (REPO_DIR / "docs" / "contenido" / "cobertura.md").read_text(
        encoding="utf-8"
    ) == expected
    assert not [i for i in issues if i.severity == "error"]
