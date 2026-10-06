"""Carga de una ruta de contenido desde YAML (contrato §9). No toca la base de datos."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import TypeAdapter, ValidationError

from app.modules.content.schema import (
    AssessmentFormFile,
    AudioManifest,
    ItemFile,
    LessonFile,
    ObjectivesFile,
    PathFile,
    RubricsFile,
    ScenarioFile,
    SourcesFile,
)

Severity = Literal["error", "warning"]
ITEM_ADAPTER: TypeAdapter[LessonFile | ScenarioFile | AssessmentFormFile] = TypeAdapter(ItemFile)
REGISTRY_FILES = ("path.yaml", "objectives.yaml", "sources.yaml", "rubrics.yaml")


@dataclass(frozen=True)
class Issue:
    severity: Severity
    code: str
    file: str
    message: str
    activity: str | None = None

    def render(self) -> str:
        where = f"{self.file}" + (f" [{self.activity}]" if self.activity else "")
        return f"{self.severity}: {self.code}: {where}: {self.message}"


@dataclass
class LoadedItem:
    file: str
    raw_text: str
    model: LessonFile | ScenarioFile | AssessmentFormFile | None


@dataclass
class ContentBundle:
    root: Path
    path_dir: Path
    path: PathFile | None = None
    objectives: ObjectivesFile | None = None
    sources: SourcesFile | None = None
    rubrics: RubricsFile | None = None
    audio: AudioManifest = field(default_factory=AudioManifest)
    items: list[LoadedItem] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    registry_texts: dict[str, str] = field(default_factory=dict)

    def rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    @property
    def valid_items(self) -> list[LessonFile | ScenarioFile | AssessmentFormFile]:
        return [i.model for i in self.items if i.model is not None]


def discover_paths(content_root: Path) -> list[Path]:
    """Directorios de ruta: los que tienen `path.yaml`. `_legacy` nunca se importa."""
    return sorted(
        p.parent for p in content_root.glob("*/path.yaml") if not p.parent.name.startswith("_")
    )


def _format_validation(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors()[:5]:
        loc = ".".join(str(x) for x in err.get("loc", ()))
        parts.append(f"{loc}: {err.get('msg')}")
    more = "" if len(exc.errors()) <= 5 else f" (+{len(exc.errors()) - 5} más)"
    return "; ".join(parts) + more


def _read_yaml(path: Path) -> tuple[Any, str]:
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(text), text


def load_path_dir(path_dir: Path, content_root: Path | None = None) -> ContentBundle:
    root = content_root or path_dir.parent
    bundle = ContentBundle(root=root, path_dir=path_dir)

    def registry(name: str, model: type[Any]) -> Any:
        file = path_dir / name
        if not file.exists():
            bundle.issues.append(
                Issue("error", "missing_file", bundle.rel(file), "falta el archivo")
            )
            return None
        try:
            data, text = _read_yaml(file)
            bundle.registry_texts[bundle.rel(file)] = text
            return model.model_validate(data)
        except (yaml.YAMLError, ValidationError) as exc:
            msg = _format_validation(exc) if isinstance(exc, ValidationError) else str(exc)
            bundle.issues.append(Issue("error", "schema", bundle.rel(file), msg))
            return None

    bundle.path = registry("path.yaml", PathFile)
    bundle.objectives = registry("objectives.yaml", ObjectivesFile)
    bundle.sources = registry("sources.yaml", SourcesFile)
    bundle.rubrics = registry("rubrics.yaml", RubricsFile)
    manifest = path_dir / "audio" / "manifest.yaml"
    if manifest.exists():
        loaded = registry("audio/manifest.yaml", AudioManifest)
        if loaded is not None:
            bundle.audio = loaded

    item_files = sorted(
        p
        for p in path_dir.rglob("*.yaml")
        if p.name not in REGISTRY_FILES and "audio" not in p.relative_to(path_dir).parts
    )
    for file in item_files:
        rel = bundle.rel(file)
        try:
            data, text = _read_yaml(file)
        except yaml.YAMLError as exc:
            bundle.issues.append(Issue("error", "schema", rel, f"YAML inválido: {exc}"))
            bundle.items.append(LoadedItem(rel, file.read_text(encoding="utf-8"), None))
            continue
        try:
            model = ITEM_ADAPTER.validate_python(data)
        except ValidationError as exc:
            bundle.issues.append(Issue("error", "schema", rel, _format_validation(exc)))
            bundle.items.append(LoadedItem(rel, text, None))
            continue
        bundle.items.append(LoadedItem(rel, text, model))
    return bundle
