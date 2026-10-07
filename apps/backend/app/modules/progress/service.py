"""Casos de uso de progreso.

- `record_outcome` participa en la transacción del intento (REQ-14: los repasos se
  actualizan en la misma transacción).
- `ProgressService`: métricas de REQ-13 con denominadores, repasos vencidos y el siguiente
  (REQ-14) y la acción "Continuar" del inicio (REQ-09). Los vencidos se calculan al pedirlos.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import NotFound
from app.db.uow import UnitOfWorkFactory
from app.modules.content import service_delivery
from app.modules.content.service_delivery import DeliveryService
from app.modules.practice import domain as practice_domain
from app.modules.practice import service_facts as facts
from app.modules.progress import domain, repository
from app.modules.progress.models import ReviewSchedule


def record_outcome(
    s: Session,
    *,
    user_id: uuid.UUID,
    objectives: list[str],
    outcome: domain.Outcome,
    aided: bool,
    mode: domain.AttemptMode,
    first_attempt: bool,
    now: datetime,
    intervals_hours: tuple[int, ...],
) -> list[str]:
    """Aplica la regla 1/3/7 a cada objetivo del intento. Devuelve los objetivos cuyo
    repaso cambió."""
    changed = []
    for code in objectives:
        row = s.scalar(
            select(ReviewSchedule)
            .where(ReviewSchedule.user_id == user_id, ReviewSchedule.objective_code == code)
            .with_for_update()
        )
        current = (
            domain.ReviewState(row.stage, row.due_at, row.last_outcome) if row is not None else None
        )
        nxt = domain.next_review_state(
            current,
            outcome=outcome,
            aided=aided,
            mode=mode,
            first_attempt=first_attempt,
            now=now,
            intervals_hours=intervals_hours,
        )
        if nxt is None:
            continue
        if row is None:
            s.add(
                ReviewSchedule(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    objective_code=code,
                    stage=nxt.stage,
                    due_at=nxt.due_at,
                    last_outcome=nxt.last_outcome,
                    updated_at=now,
                )
            )
        else:
            row.stage, row.due_at, row.last_outcome, row.updated_at = (
                nxt.stage,
                nxt.due_at,
                nxt.last_outcome,
                now,
            )
        changed.append(code)
    return changed


def review_snapshot(
    s: Session, user_id: uuid.UUID, objectives: list[str]
) -> dict[str, dict[str, Any] | None]:
    """Estado de los repasos de esos objetivos (bloqueados), para poder deshacer un cambio."""
    out: dict[str, dict[str, Any] | None] = {}
    for code in objectives:
        row = s.scalar(
            select(ReviewSchedule)
            .where(ReviewSchedule.user_id == user_id, ReviewSchedule.objective_code == code)
            .with_for_update()
        )
        out[code] = (
            None
            if row is None
            else {
                "stage": row.stage,
                "due_at": row.due_at.isoformat(),
                "last_outcome": row.last_outcome,
            }
        )
    return out


def restore_reviews(
    s: Session,
    user_id: uuid.UUID,
    before: dict[str, dict[str, Any] | None],
    after: dict[str, dict[str, Any] | None],
    now: datetime,
) -> list[str]:
    """Devuelve cada repaso a `before` solo si sigue como lo dejó el cambio (`after`): si otra
    práctica lo movió después, no se toca. Devuelve los objetivos restaurados."""
    restored = []
    current = review_snapshot(s, user_id, list(before))
    for code, previous in before.items():
        if current.get(code) != after.get(code) or current.get(code) is None:
            continue
        row = s.scalar(
            select(ReviewSchedule).where(
                ReviewSchedule.user_id == user_id, ReviewSchedule.objective_code == code
            )
        )
        assert row is not None
        if previous is None:
            s.delete(row)
        else:
            row.stage = int(previous["stage"])
            row.due_at = datetime.fromisoformat(str(previous["due_at"]))
            row.last_outcome = str(previous["last_outcome"])
            row.updated_at = now
        restored.append(code)
    return restored


@dataclass(frozen=True)
class Viewer:
    user_id: uuid.UUID
    timezone: str


def _schedule_row(row: ReviewSchedule, now: datetime) -> dict[str, Any]:
    return {
        "objective": row.objective_code,
        "stage": row.stage,
        "due_at": row.due_at.isoformat(),
        "due": row.due_at <= now,
        "last_outcome": row.last_outcome,
    }


class ProgressService:
    def __init__(self, uow: UnitOfWorkFactory, clock: Clock, settings: Settings) -> None:
        self.uow = uow
        self.clock = clock
        self.settings = settings

    def progress(self, viewer: Viewer) -> dict[str, Any]:
        now = self.clock.now()
        since = now - timedelta(days=domain.METRIC_DAYS)
        with self.uow() as s:
            path_id = facts.current_path_id(s, viewer.user_id)
            attempts = facts.attempts(s, viewer.user_id)
            lessons = facts.lessons(s, viewer.user_id, path_id) if path_id else []
            aids = facts.aid_counts(s, viewer.user_id, since)
            schedule = repository.schedule_of(s, viewer.user_id)
            diagnostic = facts.diagnostic_pending(s, viewer.user_id, path_id) if path_id else None
        units = self._unit_titles(path_id)
        advance = domain.lesson_advance(lessons)
        for row in advance["units"]:
            row["title"] = units.get(row["unit"], row["unit"])
        due = [r for r in schedule if r.due_at <= now]
        today = practice_domain.local_day(now, viewer.timezone)
        return {
            "period_days": domain.METRIC_DAYS,
            "advance": advance,
            "initial_accuracy": domain.initial_accuracy(attempts, since),
            "delayed_recall": domain.delayed_recall(attempts, since),
            "aids": {kind: aids.get(kind, 0) for kind in practice_domain.AID_KINDS},
            "production": domain.production(attempts),
            "to_reinforce": domain.to_reinforce(attempts, since),
            "streak_days": domain.streak({a.local_day for a in attempts}, today),
            "reviews_due": len(due),
            "next_action": self._next_action(lessons, due),
            "diagnostic_form_id": str(diagnostic) if diagnostic else None,
        }

    def _unit_titles(self, path_id: uuid.UUID | None) -> dict[str, str]:
        if path_id is None:
            return {}
        try:
            detail = DeliveryService(self.uow).path_detail(path_id)
        except NotFound:
            return {}
        return {u["slug"]: u["title"] for u in detail["units"]}

    @staticmethod
    def _next_action(lessons: list[facts.LessonFact], due: list[ReviewSchedule]) -> dict[str, Any]:
        """REQ-09: lección en curso → repaso vencido → siguiente lección recomendada."""
        in_progress = next((x for x in lessons if x.started and not x.completed), None)
        if in_progress is not None:
            return _lesson_action(in_progress, "in_progress")
        if due:
            return {"kind": "review", "objective": due[0].objective_code}
        nxt = domain.next_lesson(lessons)
        if nxt is not None:
            return _lesson_action(nxt, "next")
        return {"kind": "done"}

    def reviews(self, viewer: Viewer) -> dict[str, Any]:
        now = self.clock.now()
        with self.uow() as s:
            rows = [_schedule_row(r, now) for r in repository.schedule_of(s, viewer.user_id)]
        return {
            "due": [r for r in rows if r["due"]],
            "upcoming": [r for r in rows if not r["due"]],
        }

    def next_review(self, viewer: Viewer, objective: str | None) -> dict[str, Any]:
        """El siguiente repaso vencido (el más antiguo primero). Con `objective`, la
        reparación inmediata opcional de ese objetivo aunque aún no venza (REQ-14)."""
        now = self.clock.now()
        with self.uow() as s:
            path_id = facts.current_path_id(s, viewer.user_id)
            schedule = repository.schedule_of(s, viewer.user_id)
            if objective is not None:
                rows = [r for r in schedule if r.objective_code == objective]
                order = [objective]
            else:
                rows = [r for r in schedule if r.due_at <= now]
                order = [r.objective_code for r in rows]
            by_code = {r.objective_code: r for r in schedule}
            for code in order:
                if path_id is None:
                    break
                chosen = domain.choose_review(
                    facts.review_candidates(s, viewer.user_id, path_id, code)
                )
                if chosen is None:
                    continue
                candidate, repeated = chosen
                found = service_delivery.review_activity(s, candidate.activity_id)
                if found is None:
                    continue
                row = by_code.get(code)
                return {
                    "review": {
                        "objective": code,
                        "due": bool(row and row.due_at <= now),
                        "stage": row.stage if row else None,
                        "repeated": repeated,
                        **found,
                    },
                    "remaining_due": len(rows),
                }
        return {"review": None, "remaining_due": 0}


def _lesson_action(lesson: domain.LessonLike, reason: str) -> dict[str, Any]:
    return {
        "kind": lesson.kind,
        "item_id": str(lesson.item_id),
        "title": lesson.title,
        "reason": reason,
    }
