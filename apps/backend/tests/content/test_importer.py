"""Importación idempotente (REQ-07): dos veces no crea revisiones; un archivo inválido no
escribe nada; nunca aprueba ni publica."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.content.importer import ImportAborted
from app.modules.content.models import Activity, ContentItem, ContentRevision, LearningPath
from app.modules.content.service_editorial import EditorialService
from tests.content.builder import PATH_SLUG


def _count(db: Session, model: Any) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


def test_import_creates_draft_revisions(imported: Path, db: Session) -> None:
    revisions = db.scalars(select(ContentRevision)).all()
    assert len(revisions) == 4
    assert {r.status for r in revisions} == {"draft"}
    assert all(r.source_path.startswith("content/ruta-prueba/units/") for r in revisions)
    assert all(len(r.content_hash) == 64 for r in revisions)
    path = db.scalar(select(LearningPath).where(LearningPath.code == PATH_SLUG))
    assert path is not None
    assert (
        db.scalar(
            select(func.count())
            .select_from(ContentItem)
            .where(ContentItem.published_revision_id.is_not(None))
        )
        == 0
    )
    assert _count(db, Activity) == 8 + 2 + 1 + 7


def test_import_twice_creates_nothing_new(
    editorial: EditorialService, imported: Path, db: Session
) -> None:
    before = _count(db, ContentRevision)
    (result,) = editorial.import_dir(imported)
    assert result.created == []
    assert len(result.refreshed) == 4
    assert _count(db, ContentRevision) == before


def test_editing_a_file_creates_a_new_draft_version(
    editorial: EditorialService, imported: Path, db: Session
) -> None:
    file = imported / PATH_SLUG / "units/u1/l1-lectura.yaml"
    data = yaml.safe_load(file.read_text())
    data["title"] = "Elegir un curso (v2)"
    file.write_text(yaml.safe_dump(data, allow_unicode=True))
    (result,) = editorial.import_dir(imported)
    assert result.created == ["u1-l1-lectura v2"]
    versions = db.scalars(
        select(ContentRevision.version)
        .join(ContentItem, ContentItem.id == ContentRevision.item_id)
        .where(ContentItem.slug == "u1-l1-lectura")
    ).all()
    assert sorted(versions) == [1, 2]


def test_status_change_does_not_create_a_revision(
    editorial: EditorialService, imported: Path, db: Session
) -> None:
    file = imported / PATH_SLUG / "units/u1/l1-lectura.yaml"
    data = yaml.safe_load(file.read_text())
    data["status"] = "ready-for-review"
    file.write_text(yaml.safe_dump(data, allow_unicode=True))
    (result,) = editorial.import_dir(imported)
    assert result.created == []
    rev = db.scalar(
        select(ContentRevision)
        .join(ContentItem, ContentItem.id == ContentRevision.item_id)
        .where(ContentItem.slug == "u1-l1-lectura")
    )
    assert rev is not None and rev.file_status == "ready-for-review"


def test_invalid_content_writes_nothing(
    editorial: EditorialService, imported: Path, db: Session
) -> None:
    before = (_count(db, ContentRevision), _count(db, Activity))
    file = imported / PATH_SLUG / "units/u1/l3-escritura.yaml"
    data = yaml.safe_load(file.read_text())
    data["title"] = "Pedir información TODO"
    data["activities"][0]["rubric"] = "inexistente"
    file.write_text(yaml.safe_dump(data, allow_unicode=True))
    lesson = imported / PATH_SLUG / "units/u1/l1-lectura.yaml"
    other = yaml.safe_load(lesson.read_text())
    other["title"] = "Cambio que no debe entrar"
    lesson.write_text(yaml.safe_dump(other, allow_unicode=True))
    with pytest.raises(ImportAborted) as exc:
        editorial.import_dir(imported)
    assert {i.code for i in exc.value.issues} >= {"forbidden_marker", "unknown_rubric"}
    assert (_count(db, ContentRevision), _count(db, Activity)) == before


def test_activities_split_public_and_private_columns(imported: Path, db: Session) -> None:
    act = db.scalar(select(Activity).where(Activity.activity_key == "u1.l1.p1"))
    assert act is not None
    # Las opciones se guardan en un orden determinista por actividad, no en el del archivo.
    assert act.options == {
        "options": [
            {"id": "c", "text": "Neither course, option 1"},
            {"id": "a", "text": "Course A, option 1"},
            {"id": "b", "text": "Course B, option 1"},
        ],
        "multiple": False,
    }
    assert act.solution == {"correct": ["a"], "why": {"b": "Es en sábado."}}
    assert act.hints == ["Busca los días de cada curso."]
    assert act.explanation and act.support_es
