"""MVP-02 REQ-05 (feedback final de voz) con el evaluador falso: AC-12 (sin consentimiento no
hay feedback; exportación y borrado de transcripciones), AC-13 (un turno disputado oculta las
observaciones con evidencia en él), repaso por dificultad confirmada, idempotencia, mínimo de
30 s de voz y la valoración de la sesión (REQ-06)."""

from __future__ import annotations

import json
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.bootstrap import Container
from app.core.clock import FakeClock
from app.core.config import Settings
from app.db.uow import UnitOfWorkFactory
from app.modules.coaching.feedback.adapters.fake import FakeFeedbackEvaluator
from app.modules.coaching.voice.models import VoiceSession
from app.modules.content.models import ContentRevision
from app.modules.insights.models import UserFeedback
from app.modules.progress.models import ReviewSchedule
from app.modules.usage.models import AiRun
from tests.conftest import FAST_PASSWORDS
from tests.content.builder import write_content
from tests.helpers import Account, AccountFactory

FUNDED = {
    "ai_feedback_enabled": True,
    "budget_global_monthly_microusd": 5_000_000,
    "budget_user_monthly_microusd": 1_000_000,
    "gemini_price_input_per_mtok_microusd": 100_000,
    "gemini_price_output_per_mtok_microusd": 400_000,
    "feedback_provider": "fake",
}
TURNS: list[dict[str, Any]] = [
    {"n": 1, "role": "coach", "text": "Hi! How can I help you today?", "at_s": 0.0, "aid": False},
    {
        "n": 2,
        "role": "learner",
        "text": "I would like to join an evening course this month.",
        "at_s": 3.0,
        "aid": False,
    },
    {"n": 3, "role": "coach", "text": "We have groups on Monday.", "at_s": 8.0, "aid": False},
    {
        "n": 4,
        "role": "learner",
        "text": "Could you repeat that, please?",
        "at_s": 11.0,
        "aid": True,
    },
    {
        "n": 5,
        "role": "learner",
        "text": "How much does the course cost for one month?",
        "at_s": 15.0,
        "aid": False,
    },
    {"n": 6, "role": "coach", "text": "It is ninety dollars.", "at_s": 20.0, "aid": False},
]


@pytest.fixture
def evaluator() -> FakeFeedbackEvaluator:
    return FakeFeedbackEvaluator()


@pytest.fixture
def content_root(tmp_path: Path) -> Path:
    """La ruta de prueba con dos criterios en la rúbrica `transfer` (dos observaciones)."""

    def two_criteria(files: dict[str, Any]) -> None:
        for rubric in files["rubrics.yaml"]["rubrics"]:
            if rubric["id"] == "transfer":
                rubric["criteria"].append(
                    {
                        "id": "language",
                        "name_es": "Lenguaje",
                        "levels": [{"score": n, "descriptor_es": f"Nivel {n}"} for n in range(4)],
                    }
                )

    return write_content(tmp_path / "voz", two_criteria)


@pytest.fixture
def container(
    settings: Settings,
    uow: UnitOfWorkFactory,
    clock: FakeClock,
    evaluator: FakeFeedbackEvaluator,
    content_root: Path,
) -> Container:
    return Container(
        settings=settings.model_copy(update={**FUNDED, "content_dir": content_root}),
        uow=uow,
        clock=clock,
        passwords=FAST_PASSWORDS,
        feedback_evaluator=evaluator,
        ready_providers=frozenset({"ai_feedback"}),
    )


@pytest.fixture
def scenario(admin: Account, editorial: Any, content_root: Path) -> tuple[uuid.UUID, uuid.UUID]:
    """Publica la ruta de prueba; devuelve el escenario y su revisión publicada."""
    editorial.import_dir(content_root)
    found: tuple[uuid.UUID, uuid.UUID] | None = None
    for rev in admin.client.get("/api/v1/admin/content/revisions").json():
        admin.client.post(
            f"/api/v1/admin/content/revisions/{rev['id']}/approve",
            json={"content_hash": rev["content_hash"]},
            headers=admin.headers(),
        )
        res = admin.client.post(
            f"/api/v1/admin/content/revisions/{rev['id']}/publish", json={}, headers=admin.headers()
        )
        assert res.status_code == 200, res.text
        if rev["item_slug"] == "u1-escenario":
            found = (uuid.UUID(rev["item_id"]), uuid.UUID(rev["id"]))
    assert found is not None
    return found


def ended_session(
    db: Session,
    clock: FakeClock,
    user_id: uuid.UUID,
    scenario: tuple[uuid.UUID, uuid.UUID],
    *,
    save: bool = True,
    speech_ms: int = 45_000,
    status: str = "ended",
    transcript: list[dict[str, Any]] | None = None,
) -> str:
    now = clock.now()
    row = VoiceSession(
        id=uuid.uuid4(),
        user_id=user_id,
        scenario_item_id=scenario[0],
        scenario_revision_id=scenario[1],
        status=status,
        max_seconds=300,
        save_transcript=save,
        created_at=now - timedelta(minutes=6),
        deadline_at=now - timedelta(seconds=30),
        connected_at=now - timedelta(minutes=6),
        started_at=now - timedelta(minutes=6),
        ended_at=None if status == "active" else now - timedelta(minutes=1),
        end_reason=None if status == "active" else "user_stop",
        learner_speech_ms=speech_ms,
        aids=[{"kind": "repeat", "at_s": 11.0}],
        transcript=(transcript or TURNS) if save else None,
    )
    db.add(row)
    db.flush()
    return str(row.id)


def ask(acct: Account, session_id: str, key: str | None = None) -> Any:
    return acct.client.post(
        f"/api/v1/voice-sessions/{session_id}/feedback",
        headers={**acct.headers(), "Idempotency-Key": key or str(uuid.uuid4())},
    )


def dispute(acct: Account, session_id: str, n: int) -> Any:
    return acct.post(f"/api/v1/voice-sessions/{session_id}/turns/{n}/flag")


def reviews(db: Session, user_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(ReviewSchedule)
            .where(ReviewSchedule.user_id == user_id)
        )
        or 0
    )


def test_final_feedback_quotes_learner_turns_and_schedules_a_review(
    student: Account,
    scenario: tuple[uuid.UUID, uuid.UUID],
    db: Session,
    clock: FakeClock,
    evaluator: FakeFeedbackEvaluator,
) -> None:
    session_id = ended_session(db, clock, student.id, scenario)
    res = ask(student, session_id, key="22222222-2222-4222-8222-222222222222")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "evaluable" and body["label"] == "Feedback automático orientativo (IA)"
    assert [o["turn"] for o in body["observations"]] == [2, 5]  # hasta dos, con su turno
    assert [o["criterion_name_es"] for o in body["observations"]] == ["Tarea", "Lenguaje"]
    assert body["hidden"] == 0 and body["rubric_levels"] == {"task": 2, "language": 2}
    # Solo los turnos del alumno, sin la ayuda, con la rúbrica y la situación del escenario.
    (call,) = evaluator.calls
    assert call.kind == "voice" and call.prompt_version == "voice-v1"
    assert call.max_observations == 2 and call.rubric_id == "transfer"
    assert "repeat that" not in call.learner_text and " | " in call.learner_text
    assert "ask_price" in call.task_en
    run = db.get(AiRun, uuid.UUID(body["run_id"]))
    assert run is not None and run.status == "succeeded" and run.purpose == "speaking_feedback"
    assert run.voice_session_id == uuid.UUID(session_id)
    row = db.get(VoiceSession, uuid.UUID(session_id))
    assert row is not None
    db.refresh(row)
    assert row.feedback is not None and row.feedback["status"] == "evaluable"
    assert reviews(db, student.id) == 1  # dificultad confirmada → repaso del objetivo
    detail = student.client.get(f"/api/v1/voice-sessions/{session_id}").json()
    assert detail["feedback"]["observations"] == body["observations"]
    # La misma clave o una nueva no vuelven a llamar ni a cobrar.
    assert ask(student, session_id, key="22222222-2222-4222-8222-222222222222").json() == body
    assert ask(student, session_id).json() == body
    assert len(evaluator.calls) == 1


def test_a_disputed_turn_hides_its_observations(
    student: Account,
    scenario: tuple[uuid.UUID, uuid.UUID],
    db: Session,
    clock: FakeClock,
) -> None:
    session_id = ended_session(db, clock, student.id, scenario)
    body = ask(student, session_id).json()
    assert len(body["observations"]) == 2
    res = dispute(student, session_id, 5)
    assert res.status_code == 200, res.text
    turns = {t["n"]: t for t in res.json()["transcript"]}
    assert turns[5]["disputed"] and not turns[2]["disputed"]
    shown = res.json()["feedback"]
    assert [o["turn"] for o in shown["observations"]] == [2] and shown["hidden"] == 1
    # Marcar otra vez no cambia nada; las del coach y las inexistentes no se marcan.
    assert dispute(student, session_id, 5).status_code == 200
    assert dispute(student, session_id, 1).status_code == 422
    assert dispute(student, session_id, 99).status_code == 422
    again = ask(student, session_id).json()
    assert [o["turn"] for o in again["observations"]] == [2] and again["hidden"] == 1


def test_disputes_before_the_feedback_do_not_confirm_a_difficulty(
    student: Account,
    scenario: tuple[uuid.UUID, uuid.UUID],
    db: Session,
    clock: FakeClock,
) -> None:
    session_id = ended_session(db, clock, student.id, scenario)
    for n in (2, 5):
        assert dispute(student, session_id, n).status_code == 200
    body = ask(student, session_id).json()
    assert body["status"] == "evaluable" and body["observations"] == [] and body["hidden"] == 2
    assert reviews(db, student.id) == 0  # reconocimiento dudoso, no error del alumno


def test_without_consent_or_enough_speech_there_is_no_call(
    student: Account,
    scenario: tuple[uuid.UUID, uuid.UUID],
    db: Session,
    clock: FakeClock,
    evaluator: FakeFeedbackEvaluator,
) -> None:
    no_consent = ended_session(db, clock, student.id, scenario, save=False)
    body = ask(student, no_consent).json()
    assert body["status"] == "not_evaluable" and body["reason"] == "no_consent"
    row = db.get(VoiceSession, uuid.UUID(no_consent))
    assert row is not None and row.feedback is None and row.transcript is None
    short = ended_session(db, clock, student.id, scenario, speech_ms=12_000)
    body = ask(student, short).json()
    assert body["status"] == "not_evaluable" and body["reason"] == "too_little_speech"
    assert evaluator.calls == []
    assert db.scalar(select(func.count()).select_from(AiRun)) == 0


def test_open_foreign_and_failed_sessions(
    student: Account,
    make_account: AccountFactory,
    scenario: tuple[uuid.UUID, uuid.UUID],
    db: Session,
    clock: FakeClock,
    evaluator: FakeFeedbackEvaluator,
) -> None:
    live = ended_session(db, clock, student.id, scenario, status="active")
    res = ask(student, live)
    assert res.status_code == 409 and res.json()["error"]["code"] == "voice_session_open"
    other = make_account("otra-voz@example.com")
    mine = ended_session(db, clock, student.id, scenario)
    assert ask(other, mine).status_code == 404
    assert dispute(other, mine, 2).status_code == 404
    assert other.client.get(f"/api/v1/voice-sessions/{mine}").status_code == 404
    # Un fallo del proveedor se libera y se puede reintentar; el reintento sí llama.
    failing = [dict(t) for t in TURNS]
    failing[1]["text"] = "I would like to join an evening course [[fake:failed]] this month."
    flaky = ended_session(db, clock, student.id, scenario, transcript=failing)
    first = ask(student, flaky).json()
    assert first["status"] == "failed" and first["reason"] == "http_503"
    run = db.get(AiRun, uuid.UUID(first["run_id"]))
    assert run is not None and run.status == "failed"
    second = ask(student, flaky).json()
    assert second["status"] == "failed" and len(evaluator.calls) == 2


def test_session_rating_is_only_for_the_owner(
    student: Account,
    make_account: AccountFactory,
    scenario: tuple[uuid.UUID, uuid.UUID],
    db: Session,
    clock: FakeClock,
) -> None:
    session_id = ended_session(db, clock, student.id, scenario)
    res = student.post(
        "/api/v1/feedback",
        json={"context_type": "voice", "context_id": session_id, "rating": 4},
    )
    assert res.status_code == 201, res.text  # type: ignore[attr-defined]
    other = make_account("otra-valora@example.com")
    foreign = other.post(
        "/api/v1/feedback",
        json={"context_type": "voice", "context_id": session_id, "rating": 1},
    )
    assert foreign.status_code == 404  # type: ignore[attr-defined]
    missing = student.post("/api/v1/feedback", json={"context_type": "voice", "rating": 3})
    assert missing.status_code == 422  # type: ignore[attr-defined]
    rows = db.scalars(select(UserFeedback).where(UserFeedback.context_type == "voice")).all()
    assert [(r.user_id, r.rating) for r in rows] == [(student.id, 4)]


def test_export_includes_and_delete_removes_voice_transcripts(
    student: Account,
    scenario: tuple[uuid.UUID, uuid.UUID],
    db: Session,
    clock: FakeClock,
) -> None:
    session_id = ended_session(db, clock, student.id, scenario)
    ask(student, session_id)
    exported = student.client.get("/api/v1/me/export").json()
    (row,) = exported["tables"]["voice_sessions"]
    assert row["id"] == session_id
    assert "How much does the course cost" in json.dumps(row["transcript"])
    assert row["feedback"]["status"] == "evaluable"
    res = student.client.request(
        "DELETE", "/api/v1/me", json={"password": student.password}, headers=student.headers()
    )
    assert res.status_code == 204
    left = db.scalar(
        select(func.count()).select_from(VoiceSession).where(VoiceSession.user_id == student.id)
    )
    assert left == 0


def test_pilot_panel_counts_disputed_turns_and_session_ratings(
    student: Account,
    admin: Account,
    scenario: tuple[uuid.UUID, uuid.UUID],
    db: Session,
    clock: FakeClock,
) -> None:
    session_id = ended_session(db, clock, student.id, scenario)
    dispute(student, session_id, 5)
    student.post(
        "/api/v1/feedback", json={"context_type": "voice", "context_id": session_id, "rating": 5}
    )
    voice_ai = admin.client.get("/api/v1/admin/pilot/summary").json()["voice_ai"]
    assert voice_ai["disputed_turns"] == 1
    assert voice_ai["voice_ratings"] == 1 and voice_ai["voice_rating_average"] == 5.0
    # El panel nunca lleva texto de la transcripción.
    assert "How much" not in json.dumps(voice_ai)


def test_revision_of_the_scenario_carries_the_rubric(
    scenario: tuple[uuid.UUID, uuid.UUID], db: Session
) -> None:
    rev = db.get(ContentRevision, scenario[1])
    assert rev is not None and rev.body["rubric"] == "transfer"
