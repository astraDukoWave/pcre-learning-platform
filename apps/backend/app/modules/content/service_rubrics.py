"""Rúbricas por id desde los archivos de contenido (`CONTENT_DIR/*/rubrics.yaml`), los mismos
que importa la release. La revisión de un escenario guarda solo el id de su rúbrica; el
feedback final de voz (MVP-02 REQ-05) necesita sus criterios y niveles."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.modules.content.schema import RubricsFile


@lru_cache(maxsize=4)
def _rubrics(content_dir: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(Path(content_dir).glob("*/rubrics.yaml")):
        data = RubricsFile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        for rubric in data.rubrics:
            out[rubric.id] = rubric.model_dump(mode="json")
    return out


def rubric_by_id(content_dir: Path, rubric_id: str) -> dict[str, Any] | None:
    return _rubrics(str(content_dir)).get(rubric_id)
