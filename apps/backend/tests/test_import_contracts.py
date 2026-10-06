"""NFR-12 / AC-04: los contratos de import-linter se prueban, no se suponen.

Cada caso copia `app/` a un directorio temporal, agrega un módulo que rompe una regla y
comprueba que `lint-imports` falla con esa regla rota.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
LINT_IMPORTS = str(Path(sys.executable).parent / "lint-imports")


def _run(cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [LINT_IMPORTS, "--no-cache"], cwd=cwd, capture_output=True, text=True, check=False
    )


def _copy_tree(tmp_path: Path) -> Path:
    root = tmp_path / "backend"
    root.mkdir()
    shutil.copytree(BACKEND / "app", root / "app", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(BACKEND / ".importlinter", root / ".importlinter")
    shutil.copy(BACKEND / "import_contracts.py", root / "import_contracts.py")
    return root


def _write(root: Path, rel: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    for parent in path.relative_to(root).parents:
        if str(parent) != ".":
            (root / parent / "__init__.py").touch()
    path.write_text(body)


def test_current_tree_keeps_every_contract() -> None:
    result = _run(BACKEND)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "4 kept, 0 broken" in result.stdout


VIOLATIONS = {
    "domain_imports_sqlalchemy": (
        {"app/modules/zz/domain.py": "import sqlalchemy\n"},
        "Regla 1",
    ),
    "domain_imports_db_indirectly": (
        {
            "app/modules/zz/domain.py": "from app.modules.zz import helpers\n",
            "app/modules/zz/helpers.py": "from app.db import base\n",
        },
        "Regla 1",
    ),
    "service_imports_fastapi": (
        {"app/modules/zz/service_editorial.py": "import fastapi\n"},
        "Regla 2",
    ),
    "router_imports_models": (
        {
            "app/modules/zz/models.py": "X = 1\n",
            "app/modules/zz/router_admin.py": "from app.modules.zz import models\n",
        },
        "Regla 3",
    ),
    "module_imports_other_repository": (
        {
            "app/modules/aa/repository.py": "X = 1\n",
            "app/modules/zz/service.py": "from app.modules.aa import repository\n",
        },
        "Regla 4",
    ),
}


@pytest.mark.parametrize("case", sorted(VIOLATIONS))
def test_violation_breaks_lint_imports(tmp_path: Path, case: str) -> None:
    files, rule = VIOLATIONS[case]
    root = _copy_tree(tmp_path)
    for rel, body in files.items():
        _write(root, rel, body)
    result = _run(root)
    assert result.returncode != 0, result.stdout
    broken = [line for line in result.stdout.splitlines() if line.endswith("BROKEN")]
    assert any(line.startswith(rule) for line in broken), result.stdout


def test_repository_may_read_other_module_models(tmp_path: Path) -> None:
    root = _copy_tree(tmp_path)
    _write(root, "app/modules/zz/repository.py", "from app.modules.identity import models\n")
    result = _run(root)
    assert result.returncode == 0, result.stdout
