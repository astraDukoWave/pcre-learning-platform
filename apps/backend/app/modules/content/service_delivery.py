"""Entrega al alumno: DTO construidos con lista permitida (AC-08).

Nunca viajan soluciones, explicaciones, variantes aceptadas, pistas, apoyos,
transcripciones, ejemplos ni rúbricas antes de enviar. Las ayudas se anuncian solo como
`{"kind", "count"}` y se piden a `POST /aids`.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from sqlalchemy import select
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


def _unit_from_body(s: Session, item: ContentItem, body: dict[str, Any]) -> Unit | None:
    """La unidad que ve el alumno sale del cuerpo de la revisión (aprobado), no de la fila
    del ítem, que el importador actualiza con cada borrador."""
    slug = body.get("unit")
    if not slug:
        return None
    return s.scalar(select(Unit).where(Unit.path_id == item.path_id, Unit.slug == slug))


def unit_ref(s: Session, item: ContentItem, body: dict[str, Any]) -> dict[str, Any] | None:
    """Unidad del ítem según el cuerpo de la revisión (lo que ve el alumno)."""
    return _unit(_unit_from_body(s, item, body))


def item_dto(
    s: Session,
    item: ContentItem,
    rev: ContentRevision,
    *,
    mode: Mode = "practice",
    pools: tuple[str, ...] = ("practice",),
) -> dict[str, Any]:
    """DTO del alumno. Todo texto visible sale de `rev.body` (la revisión aprobada y
    publicada o fijada), nunca de la fila mutable del ítem (hallazgo 1 de CS-04)."""
    body = rev.body
    unit = _unit_from_body(s, item, body)
    acts = [a for a in repository.activities_of(s, rev.id) if a.pool in pools]
    dto: dict[str, Any] = {
        "id": str(item.id),
        "revision_id": str(rev.id),
        "revision_version": rev.version,
        "kind": item.kind,
        "slug": item.slug,
        "title": body["title"],
        "unit": _unit(unit),
        "objectives": list(body.get("objectives", [])),
        "activities": [student_activity(a, mode) for a in acts],
    }
    if item.kind == "lesson":
        dto.update(
            {
                "skill": body.get("skill"),
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
                "form_kind": body.get("form_kind"),
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
            refs: list[tuple[str | None, dict[str, Any]]] = []
            for item in repository.published_items(s, path.id):
                rev = repository.revision(s, item.published_revision_id)  # type: ignore[arg-type]
                if rev is None:
                    continue
                refs.append((rev.body.get("unit"), _item_ref(item, rev.body)))
            refs.sort(key=lambda r: (r[1]["position"], r[1]["slug"]))
            units = []
            for unit in repository.units_of(s, path.id):
                unit_items = [ref for slug, ref in refs if slug == unit.slug]
                if unit_items:
                    units.append({**(_unit(unit) or {}), "items": unit_items})
            forms = [ref for slug, ref in refs if slug is None]
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


def _item_ref(item: ContentItem, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "kind": item.kind,
        "slug": item.slug,
        "title": body["title"],
        "position": body["position"],
        "skill": body.get("skill"),
        "form_kind": body.get("form_kind"),
    }


def review_activity(s: Session, activity_id: uuid.UUID) -> dict[str, Any] | None:
    """Actividad del pool `review` con su ítem y los pasajes que usa, para un repaso. Misma
    lista permitida que la lección (AC-08): las ayudas se anuncian y se piden aparte."""
    act = s.get(Activity, activity_id)
    if act is None:
        return None
    rev = repository.revision(s, act.revision_id)
    item = s.get(ContentItem, rev.item_id) if rev else None
    if rev is None or item is None or item.published_revision_id != rev.id:
        return None
    passage_id = (act.stimulus or {}).get("passage")
    return {
        "item": {
            "id": str(item.id),
            "revision_id": str(rev.id),
            "kind": item.kind,
            "slug": item.slug,
            "title": rev.body["title"],
            "unit": unit_ref(s, item, rev.body),
        },
        "activity": student_activity(act, "review"),
        "passages": [p for p in rev.body.get("passages", []) if p.get("id") == passage_id],
    }
