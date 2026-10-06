"""Entrega al alumno: DTO construidos con lista permitida (AC-08).

Nunca viajan soluciones, explicaciones, variantes aceptadas, pistas, apoyos,
transcripciones, ejemplos ni rúbricas antes de enviar. Las ayudas se anuncian solo como
`{"kind", "count"}` y se piden a `POST /aids`.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.db.uow import UnitOfWorkFactory
from app.modules.content import repository
from app.modules.content.models import Activity, ContentItem, ContentRevision, Unit

Mode = Literal["practice", "review", "assessment"]

_STIMULUS_KEYS = ("text_en", "passage", "audio_url")
_OPTION_KEYS: dict[str, tuple[str, ...]] = {
    "choice": ("options", "multiple"),
    "word_completion": ("text_en", "gaps"),
    "sentence_order": ("tokens",),
    "short_writing": ("min_words", "max_words"),
    "recorded_speaking": (
        "subtype",
        "audio_url",
        "question_en",
        "prep_seconds",
        "response_seconds",
    ),
    "guided_dialogue": ("start", "nodes"),
}


def _aids(act: Activity) -> list[dict[str, Any]]:
    aids = []
    if act.hints:
        aids.append({"kind": "hint", "count": len(act.hints)})
    if act.support_es:
        aids.append({"kind": "support_es", "count": 1})
    if act.transcript:
        aids.append({"kind": "transcript", "count": 1})
    if act.example:
        aids.append({"kind": "example", "count": 1})
    return aids


def student_activity(act: Activity, mode: Mode) -> dict[str, Any]:
    stimulus = None
    if act.stimulus:
        stimulus = {k: act.stimulus[k] for k in _STIMULUS_KEYS if k in act.stimulus}
        stimulus["has_audio"] = "audio" in act.stimulus
    data: dict[str, Any] = {}
    if act.options:
        data = {k: act.options[k] for k in _OPTION_KEYS[act.format] if k in act.options}
        if act.format == "choice":
            data["options"] = [{"id": o["id"], "text": o["text"]} for o in act.options["options"]]
        if act.format == "word_completion":
            data["gaps"] = [{"id": g["id"], "shown": g["shown"]} for g in act.options["gaps"]]
        if act.format == "guided_dialogue":
            data["nodes"] = [
                {
                    "id": n["id"],
                    "speaker": n["speaker"],
                    "text_en": n["text_en"],
                    "options": [
                        {"id": o["id"], "text": o["text"], "next": o.get("next")}
                        for o in n["options"]
                    ],
                }
                for n in act.options["nodes"]
            ]
    return {
        "id": str(act.id),
        "key": act.activity_key,
        "position": act.position,
        "format": act.format,
        "task_family": act.task_family,
        "pool": act.pool,
        "objectives": list(act.objective_codes),
        "instructions_es": act.prompt.get("instructions_es", ""),
        "prompt_en": act.prompt.get("prompt_en", ""),
        "stimulus": stimulus,
        "data": data,
        "aids": [] if mode == "assessment" else _aids(act),
    }


def _unit(unit: Unit | None) -> dict[str, Any] | None:
    if unit is None:
        return None
    return {"id": str(unit.id), "slug": unit.slug, "title": unit.title, "position": unit.position}


def item_dto(
    s: Session,
    item: ContentItem,
    rev: ContentRevision,
    *,
    mode: Mode = "practice",
    pools: tuple[str, ...] = ("practice",),
) -> dict[str, Any]:
    body = rev.body
    unit = s.get(Unit, item.unit_id) if item.unit_id else None
    acts = [a for a in repository.activities_of(s, rev.id) if a.pool in pools]
    dto: dict[str, Any] = {
        "id": str(item.id),
        "revision_id": str(rev.id),
        "revision_version": rev.version,
        "kind": item.kind,
        "slug": item.slug,
        "title": item.title,
        "unit": _unit(unit),
        "objectives": list(body.get("objectives", [])),
        "activities": [student_activity(a, mode) for a in acts],
    }
    if item.kind == "lesson":
        dto.update(
            {
                "skill": item.skill,
                "objective_es": body["objective_es"],
                "pcre": body["pcre"],
                "application_task_es": body["application_task_es"],
                "passages": body.get("passages", []),
            }
        )
    elif item.kind == "scenario":
        dto.update(
            {
                "situation_es": body["situation_es"],
                "situation_en": body["situation_en"],
                "learner_role_en": body["learner_role_en"],
                "opening_en": body["opening_en"],
                "required_moves": body["required_moves"],
                "max_seconds": body.get("max_seconds", 300),
            }
        )
    else:
        dto.update(
            {
                "form_kind": item.form_kind,
                "duration_minutes": body.get("duration_minutes"),
                "passages": body.get("passages", []),
            }
        )
    return dto


class DeliveryService:
    def __init__(self, uow: UnitOfWorkFactory) -> None:
        self.uow = uow

    def list_paths(self) -> list[dict[str, Any]]:
        with self.uow() as s:
            return [
                {"id": str(p.id), "code": p.code, "title": p.title, "label": p.label}
                for p in repository.active_paths(s)
            ]

    def path_detail(self, path_id: uuid.UUID) -> dict[str, Any]:
        with self.uow() as s:
            path = next((p for p in repository.active_paths(s) if p.id == path_id), None)
            if path is None:
                raise NotFound()
            items = repository.published_items(s, path.id)
            units = []
            for unit in repository.units_of(s, path.id):
                unit_items = [i for i in items if i.unit_id == unit.id]
                if not unit_items:
                    continue
                units.append({**(_unit(unit) or {}), "items": [_item_ref(i) for i in unit_items]})
            forms = [_item_ref(i) for i in items if i.unit_id is None]
            return {
                "id": str(path.id),
                "code": path.code,
                "title": path.title,
                "label": path.label,
                "units": units,
                "assessments": forms,
            }

    def published(self, item_id: uuid.UUID, kind: str) -> dict[str, Any]:
        with self.uow() as s:
            item = s.get(ContentItem, item_id)
            if item is None or item.kind != kind or item.published_revision_id is None:
                raise NotFound()
            rev = repository.revision(s, item.published_revision_id)
            if rev is None:
                raise NotFound()
            return item_dto(s, item, rev)


def _item_ref(item: ContentItem) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "kind": item.kind,
        "slug": item.slug,
        "title": item.title,
        "position": item.position,
        "skill": item.skill,
        "form_kind": item.form_kind,
    }
