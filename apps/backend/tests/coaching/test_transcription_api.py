"""MVP-02 REQ-04 de extremo a extremo con el transcriptor falso: AC-06 (el audio nunca toca
disco, límites 413/422, comparación de la repetición), confirmación y disputa de la entrevista
con su feedback (REQ-02), idempotencia, `unknown` sin reintento, aislamiento y AC-02 (503)."""

from __future__ import annotations

import builtins
import os
import tempfile
import uuid
from typing import Any

import pytest
import starlette.formparsers
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.bootstrap import Container
from app.core.clock import FakeClock
from app.core.config import Settings
from app.db.uow import UnitOfWorkFactory
from app.modules.coaching.feedback.adapters.fake import FakeFeedbackEvaluator
from app.modules.coaching.stt.adapters.fake import FakeSpeechToText
from app.modules.insights.models import ErrorEvent
from app.modules.practice.models import Attempt
from app.modules.usage.models import AiRun, BudgetPeriod
from tests.conftest import FAST_PASSWORDS
from tests.helpers import Account, AccountFactory

FUNDED = {
    "ai_feedback_enabled": True,
    "stt_enabled": True,
    "budget_global_monthly_microusd": 5_000_000,
    "budget_user_monthly_microusd": 1_000_000,
    "gemini_price_input_per_mtok_microusd": 100_000,
    "gemini_price_output_per_mtok_microusd": 400_000,
    "feedback_provider": "fake",
    "stt_provider": "fake",
}
WEBM = "audio/webm;codecs=opus"
INTERVIEW = (
    "On weekends I usually go to the market with my family and then we cook lunch together "
    "because it is a nice way to relax after work."
)


@pytest.fixture
def stt() -> FakeSpeechToText:
    return FakeSpeechToText()


@pytest.fixture
def container(
    settings: Settings, uow: UnitOfWorkFactory, clock: FakeClock, stt: FakeSpeechToText
) -> Container:
    return Container(
        settings=settings.model_copy(update=FUNDED),
        uow=uow,
        clock=clock,
        passwords=FAST_PASSWORDS,
        feedback_evaluator=FakeFeedbackEvaluator(),
        speech_to_text=stt,
        ready_providers=frozenset({"ai_feedback", "stt"}),
    )


def record(acct: Account, all_formats: dict[str, Any], key: str, recorded: bool = True) -> str:
    act = all_formats["u1-l4-habla"]["activities"][key]
    res = acct.client.post(
        "/api/v1/attempts",
        json={"activity_id": act, "response": {"recorded": recorded}},
        headers={**acct.headers(), "Idempotency-Key": str(uuid.uuid4())},
    )
    assert res.status_code == 201, res.text
    return str(res.json()["id"])


def transcribe(
    acct: Account,
    attempt_id: str,
    activity_id: str,
    audio: bytes,
    *,
    content_type: str = WEBM,
    duration_ms: int = 4000,
    key: str | None = None,
) -> Any:
    return acct.client.post(
        "/api/v1/speaking/transcriptions",
        data={
            "attempt_id": attempt_id,
            "activity_id": activity_id,
            "duration_ms": str(duration_ms),
        },
        files={"audio": ("grabacion.webm", audio, content_type)},
        headers={**acct.headers(), "Idempotency-Key": key or str(uuid.uuid4())},
    )


def activity(all_formats: dict[str, Any], key: str) -> str:
    return str(all_formats["u1-l4-habla"]["activities"][key])


def count(db: Session, model: Any, *where: Any) -> int:
    return int(db.scalar(select(func.count()).select_from(model).where(*where)) or 0)


def user_budget(db: Session, user_id: uuid.UUID) -> tuple[int, int]:
    row = db.scalars(select(BudgetPeriod).where(BudgetPeriod.user_id == user_id)).one()
    db.refresh(row)
    return row.reserved_microusd, row.spent_microusd


def test_repeat_counts_target_words_and_never_grades(
    student: Account, all_formats: dict[str, Any], db: Session, stt: FakeSpeechToText
) -> None:
    attempt_id = record(student, all_formats, "u1.l4.p2")
    res = transcribe(
        student,
        attempt_id,
        activity(all_formats, "u1.l4.p2"),
        b"FAKE:I would like table for two please",
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "transcribed" and body["kind"] == "repeat"
    assert body["repeat"] == {
        "recognized": 7,
        "total": 8,
        "recognized_ratio": 0.875,
        "missing": ["a"],
    }
    assert "puede ser el reconocimiento" in body["hint_es"]
    assert body["words"][0] == {"word": "I", "confidence": 0.9}
    attempt = db.get(Attempt, uuid.UUID(attempt_id))
    assert attempt is not None
    db.refresh(attempt)
    # Guarda `recognized_ratio`, pero no es acierto ni error ni cierra la autoevaluación.
    assert attempt.result["transcription"]["repeat"]["recognized_ratio"] == 0.875
    assert attempt.evaluation_status == "pending" and attempt.correct is None
    assert attempt.score is None
    # 8 s del doble a USD 0.0043/min: 574 µUSD gastados; la reserva se libera.
    assert user_budget(db, student.id) == (0, 574)
    assert stt.calls == 1


def test_audio_never_touches_disk(
    student: Account,
    all_formats: dict[str, Any],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-06: 1.5 MB (más que el umbral de 1 MB en que Starlette pasa un `UploadFile` a
    disco) con todo lo que escribe archivos bloqueado durante la petición."""
    attempt_id = record(student, all_formats, "u1.l4.p2")
    marker = b"AUDIO-PRIVADO-" + uuid.uuid4().hex.encode()
    audio = b"FAKE:I would like a table for two please\n" + marker + b"\0" * (1_500_000)
    written: list[str] = []
    real_open, real_os_open = builtins.open, os.open

    def guarded_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if any(flag in mode for flag in "wax+"):
            written.append(str(file))
            raise AssertionError(f"escritura a disco: {file}")
        return real_open(file, mode, *args, **kwargs)

    def guarded_os_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT):
            written.append(str(path))
            raise AssertionError(f"escritura a disco: {path}")
        return real_os_open(path, flags, *args, **kwargs)

    def no_temp(*args: Any, **kwargs: Any) -> Any:
        written.append("tempfile")
        raise AssertionError("archivo temporal")

    with monkeypatch.context() as m:
        m.setattr(builtins, "open", guarded_open)
        m.setattr(os, "open", guarded_os_open)
        for name in ("SpooledTemporaryFile", "TemporaryFile", "NamedTemporaryFile", "mkstemp"):
            m.setattr(tempfile, name, no_temp)
        # `UploadFile` de Starlette importa la clase al cargar el módulo.
        m.setattr(starlette.formparsers, "SpooledTemporaryFile", no_temp)
        res = transcribe(student, attempt_id, activity(all_formats, "u1.l4.p2"), audio)
    assert res.status_code == 200, res.text
    assert written == []
    assert res.json()["repeat"]["recognized"] == 8
    # Ni el audio ni un trozo suyo quedan en la base.
    run = db.scalars(select(AiRun).where(AiRun.user_id == student.id)).one()
    attempt = db.get(Attempt, uuid.UUID(attempt_id))
    assert attempt is not None
    db.refresh(attempt)
    assert marker.decode() not in repr(run.output) + repr(attempt.result) + repr(attempt.response)


def test_limits_type_size_and_duration(
    student: Account, all_formats: dict[str, Any], db: Session, stt: FakeSpeechToText
) -> None:
    attempt_id = record(student, all_formats, "u1.l4.p2")
    act = activity(all_formats, "u1.l4.p2")
    big = transcribe(student, attempt_id, act, b"FAKE:x" + b"\0" * (2 * 1024 * 1024))
    assert big.status_code == 413
    huge = transcribe(student, attempt_id, act, b"\0" * (3 * 1024 * 1024))
    assert huge.status_code == 413 and huge.json()["error"]["code"] == "payload_too_large"
    long = transcribe(student, attempt_id, act, b"FAKE:hi", duration_ms=61_000)
    assert long.status_code == 422 and long.json()["error"]["code"] == "too_long"
    ogg = transcribe(student, attempt_id, act, b"FAKE:hi", content_type="audio/ogg")
    assert ogg.status_code == 422 and ogg.json()["error"]["code"] == "audio_type"
    empty = transcribe(student, attempt_id, act, b"")
    assert empty.status_code == 422 and empty.json()["error"]["code"] == "empty"
    mp4 = record(student, all_formats, "u1.l4.p2")
    assert transcribe(student, mp4, act, b"FAKE:hi", content_type="audio/mp4").status_code == 200
    # Nada de lo rechazado llegó al proveedor ni creó una ejecución.
    assert stt.calls == 1 and count(db, AiRun, AiRun.user_id == student.id) == 1


def test_audio_longer_than_declared_is_charged_but_not_shown(
    student: Account, all_formats: dict[str, Any], db: Session
) -> None:
    attempt_id = record(student, all_formats, "u1.l4.p2")
    res = transcribe(student, attempt_id, activity(all_formats, "u1.l4.p2"), b"FAKE:!long")
    assert res.status_code == 422 and res.json()["error"]["code"] == "too_long"
    run = db.scalars(select(AiRun).where(AiRun.user_id == student.id)).one()
    assert run.status == "succeeded" and run.error_code == "too_long"
    assert user_budget(db, student.id) == (0, 5375)  # 75 s transcritos sí se pagan
    attempt = db.get(Attempt, uuid.UUID(attempt_id))
    assert attempt is not None and "transcription" not in attempt.result


def test_same_key_and_later_requests_never_charge_twice(
    student: Account, all_formats: dict[str, Any], db: Session, stt: FakeSpeechToText
) -> None:
    attempt_id = record(student, all_formats, "u1.l4.p2")
    act = activity(all_formats, "u1.l4.p2")
    key = str(uuid.uuid4())
    first = transcribe(student, attempt_id, act, b"FAKE:I would like a table", key=key)
    again = transcribe(student, attempt_id, act, b"FAKE:otra cosa", key=key)
    later = transcribe(student, attempt_id, act, b"FAKE:otra cosa")
    assert first.json() == again.json() == later.json()
    assert stt.calls == 1 and count(db, AiRun, AiRun.user_id == student.id) == 1
    other = record(student, all_formats, "u1.l4.p2")
    reused = transcribe(student, other, act, b"FAKE:hola", key=key)
    assert reused.status_code == 409 and reused.json()["error"]["code"] == "idempotency_conflict"


def test_unknown_keeps_the_reservation_and_failed_can_be_retried(
    student: Account, all_formats: dict[str, Any], db: Session, stt: FakeSpeechToText
) -> None:
    act = activity(all_formats, "u1.l4.p2")
    lost = record(student, all_formats, "u1.l4.p2")
    unknown = transcribe(student, lost, act, b"FAKE:!unknown")
    assert unknown.status_code == 200 and unknown.json()["status"] == "unknown"
    assert transcribe(student, lost, act, b"FAKE:I would like").json()["status"] == "unknown"
    assert stt.calls == 1  # nunca se repite solo
    assert user_budget(db, student.id) == (4372, 0)  # la reserva completa queda comprometida
    broken = record(student, all_formats, "u1.l4.p2")
    failed = transcribe(student, broken, act, b"FAKE:!failed")
    assert failed.json()["status"] == "failed"
    assert user_budget(db, student.id) == (4372, 0)  # failed no cuesta
    retried = transcribe(student, broken, act, b"FAKE:I would like a table for two please")
    assert retried.json()["status"] == "transcribed" and stt.calls == 3


def test_interview_is_confirmed_or_disputed_before_feedback(
    student: Account, all_formats: dict[str, Any], db: Session
) -> None:
    attempt_id = record(student, all_formats, "u1.l4.p1")
    res = transcribe(
        student, attempt_id, activity(all_formats, "u1.l4.p1"), b"FAKE:" + INTERVIEW.encode()
    )
    body = res.json()
    assert body["kind"] == "interview" and body["text"] == INTERVIEW
    assert body["confirmed"] is False and body["repeat"] is None

    def feedback() -> Any:
        return student.client.post(
            f"/api/v1/attempts/{attempt_id}/feedback",
            headers={**student.headers(), "Idempotency-Key": str(uuid.uuid4())},
        )

    def decide(confirmed: bool) -> Any:
        return student.client.post(
            f"/api/v1/attempts/{attempt_id}/transcription",
            json={"confirmed": confirmed},
            headers=student.headers(),
        )

    assert feedback().json()["error"]["code"] == "feedback_not_supported"  # sin confirmar
    disputed = decide(False)
    assert disputed.status_code == 200
    assert disputed.json()["result"]["transcription"]["disputed"] is True
    assert feedback().status_code == 422  # disputada: sin feedback
    assert decide(True).json()["result"]["transcription"]["confirmed"] is True
    shown = feedback()
    assert shown.status_code == 200 and shown.json()["status"] == "evaluable"
    assert all(o["evidence"].lower() in INTERVIEW.lower() for o in shown.json()["observations"])
    run = db.scalars(
        select(AiRun).where(AiRun.user_id == student.id, AiRun.purpose == "speaking_feedback")
    ).one()
    assert run.prompt_version == "interview-v1"
    locked = decide(False)
    assert locked.status_code == 409 and locked.json()["error"]["code"] == "transcription_locked"


def test_isolation_and_unsupported_attempts(
    make_account: AccountFactory, all_formats: dict[str, Any], db: Session
) -> None:
    a, b = make_account("a@example.com"), make_account("b@example.com")
    act = activity(all_formats, "u1.l4.p2")
    mine = record(a, all_formats, "u1.l4.p2")
    assert transcribe(b, mine, act, b"FAKE:hi").status_code == 404  # ajeno
    assert transcribe(a, mine, activity(all_formats, "u1.l4.p1"), b"FAKE:hi").status_code == 404
    decided = b.client.post(
        f"/api/v1/attempts/{mine}/transcription", json={"confirmed": True}, headers=b.headers()
    )
    assert decided.status_code == 404
    silent = record(a, all_formats, "u1.l4.p2", recorded=False)
    res = transcribe(a, silent, act, b"FAKE:hi")
    assert res.status_code == 422 and res.json()["error"]["code"] == "transcription_not_supported"
    writing = all_formats["u1-l3-escritura"]["activities"]["u1.l3.p1"]
    text = a.client.post(
        "/api/v1/attempts",
        json={"activity_id": writing, "response": {"text": "I would like to join the class."}},
        headers={**a.headers(), "Idempotency-Key": str(uuid.uuid4())},
    ).json()["id"]
    assert transcribe(a, text, writing, b"FAKE:hi").status_code == 422
    no_key = a.client.post(
        "/api/v1/speaking/transcriptions",
        data={"attempt_id": mine, "activity_id": act, "duration_ms": "1000"},
        files={"audio": ("a.webm", b"FAKE:hi", WEBM)},
        headers=a.headers(),
    )
    assert no_key.status_code == 422
    missing = a.client.post(
        "/api/v1/speaking/transcriptions",
        data={"attempt_id": mine},
        files={"audio": ("a.webm", b"FAKE:hi", WEBM)},
        headers={**a.headers(), "Idempotency-Key": str(uuid.uuid4())},
    )
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "transcription_fields"
    assert count(db, AiRun) == 0


def test_without_capability_or_budget_the_answer_is_an_expected_503(
    settings: Settings,
    uow: UnitOfWorkFactory,
    clock: FakeClock,
    make_account: AccountFactory,
    all_formats: dict[str, Any],
    db: Session,
) -> None:
    """AC-02 (backend): sin STT o sin presupuesto → 503 esperado, fuera de `error_events` y
    sin ejecución; la interfaz ofrece la autoevaluación."""
    from app.main import create_app
    from tests.conftest import TEST_ORIGIN
    from tests.helpers import login

    student = make_account("sinsaldo@example.com")
    attempt_id = record(student, all_formats, "u1.l4.p2")
    for update, ready, code in (
        ({"stt_provider": "fake"}, {"stt"}, "capability_disabled"),
        ({**FUNDED, "budget_global_monthly_microusd": None}, {"stt"}, "capability_disabled"),
        (FUNDED, set(), "capability_disabled"),  # sin proveedor configurado
        ({**FUNDED, "budget_user_monthly_microusd": 1}, {"stt"}, "budget_exhausted"),
    ):
        other = Container(
            settings=settings.model_copy(update=update),
            uow=uow,
            clock=clock,
            passwords=FAST_PASSWORDS,
            speech_to_text=FakeSpeechToText(),
            ready_providers=frozenset(ready),
        )
        with TestClient(
            create_app(other.settings, container=other),
            base_url="https://testserver",
            headers={"Origin": TEST_ORIGIN},
        ) as c:
            csrf = login(c, student.email)
            res = c.post(
                "/api/v1/speaking/transcriptions",
                data={
                    "attempt_id": attempt_id,
                    "activity_id": activity(all_formats, "u1.l4.p2"),
                    "duration_ms": "4000",
                },
                files={"audio": ("a.webm", b"FAKE:hi", WEBM)},
                headers={"X-CSRF-Token": csrf, "Idempotency-Key": str(uuid.uuid4())},
            )
        assert res.status_code == 503 and res.json()["error"]["code"] == code, (update, res.text)
    assert count(db, AiRun, AiRun.user_id == student.id) == 0
    assert count(db, ErrorEvent) == 0


def test_learner_capabilities_say_only_what_is_on(student: Account, client: TestClient) -> None:
    res = student.client.get("/api/v1/capabilities")
    assert res.status_code == 200
    assert res.json() == {"ai_feedback": True, "stt": True, "voice": False}
    assert client.get("/api/v1/capabilities").status_code == 401
