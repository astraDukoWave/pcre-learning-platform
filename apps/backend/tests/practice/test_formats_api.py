"""REQ-10 y REQ-11 por la API: completado, orden y diálogo corregidos en el servidor;
autoevaluación después de enviar (NI-02) y reformulación con `revision_of`."""

from __future__ import annotations

import uuid
from typing import Any

from tests.helpers import Account, AccountFactory

TEXT = (
    "Dear Ms. Rivera, I am writing to ask about the evening English classes. Could you tell me "
    "the days and the price per month? I work until five, so I can only study after six. "
    "Thank you for your help. Best regards, Ana"
)


def attempt(acct: Account, activity_id: str, response: dict[str, Any], **extra: Any) -> Any:
    return acct.client.post(
        "/api/v1/attempts",
        json={"activity_id": activity_id, "response": response, **extra},
        headers={**acct.headers(), "Idempotency-Key": str(uuid.uuid4())},
    )


def self_assess(acct: Account, attempt_id: str, scores: dict[str, int]) -> Any:
    return acct.client.post(
        f"/api/v1/attempts/{attempt_id}/self-assessment",
        json={"scores": scores},
        headers=acct.headers(),
    )


def test_word_completion_sentence_order_and_dialogue_are_graded(
    student: Account, all_formats: dict[str, Any]
) -> None:
    writing = all_formats["u1-l3-escritura"]["activities"]
    res = attempt(student, writing["u1.l3.p4"], {"answers": {"g1": "el"}})
    assert res.status_code == 201, res.text
    assert res.json()["correct"] is True  # "trav" + "el" = travel
    res = attempt(student, writing["u1.l3.p3"], {"order": ["usually", "I", "walk", "to work"]})
    assert res.json()["correct"] is True  # segundo orden aceptado
    assert res.json()["result"]["correct_order"] == ["I", "usually", "walk", "to work"]
    res = attempt(student, writing["u1.l3.p3"], {"order": ["I", "walk", "usually", "to work"]})
    assert res.json()["correct"] is False
    dialogue = all_formats["u1-escenario"]["activities"]["u1.esc.d1"]
    res = attempt(student, dialogue, {"path": ["n1.b"]})
    body = res.json()
    assert res.status_code == 201 and body["correct"] is False
    assert body["result"]["turns"] == [
        {"step": "n1.b", "feedback_es": "Muy breve: arma una pregunta.", "good": False}
    ]
    assert attempt(student, dialogue, {"path": ["n1.c"]}).status_code == 422


def test_writing_is_pending_until_self_assessed_after_seeing_the_rubric(
    student: Account, all_formats: dict[str, Any]
) -> None:
    act = all_formats["u1-l3-escritura"]["activities"]["u1.l3.p1"]
    res = attempt(student, act, {"text": TEXT})
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["evaluation_status"] == "pending" and body["evaluation_source"] == "self"
    assert body["result"]["within_limits"] is True
    assert [c["id"] for c in body["feedback"]["rubric"]["criteria"]] == ["task"]
    assert body["feedback"]["model_commentary_es"]

    assert self_assess(student, body["id"], {}).status_code == 422
    assert self_assess(student, body["id"], {"task": 4}).status_code == 422
    assert self_assess(student, body["id"], {"other": 2}).status_code == 422
    res = self_assess(student, body["id"], {"task": 2})
    assert res.status_code == 200, res.text
    done = res.json()
    assert done["evaluation_status"] == "evaluated"
    assert done["score"] == 2 / 3 and done["result"]["self_assessment"] == {"task": 2}
    assert done["response"] == {"text": TEXT}  # la respuesta no cambia
    assert self_assess(student, body["id"], {"task": 2}).json() == done  # repetir: lo mismo
    again = self_assess(student, body["id"], {"task": 3})
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_assessed"


def test_rewrite_is_a_new_attempt_that_references_the_previous_one(
    student: Account, all_formats: dict[str, Any]
) -> None:
    acts = all_formats["u1-l3-escritura"]["activities"]
    first = attempt(student, acts["u1.l3.p1"], {"text": TEXT}).json()
    second = attempt(
        student, acts["u1.l3.p1"], {"text": TEXT + " P.S. Thanks!"}, revision_of=first["id"]
    )
    assert second.status_code == 201 and second.json()["id"] != first["id"]
    assert second.json()["first_attempt"] is False
    wrong = attempt(student, acts["u1.l3.p2"], {"text": TEXT}, revision_of=first["id"])
    assert wrong.status_code == 404  # el intento anterior es de otra actividad


def test_speaking_without_recording_is_not_evaluable(
    student: Account, all_formats: dict[str, Any]
) -> None:
    acts = all_formats["u1-l4-habla"]["activities"]
    res = attempt(student, acts["u1.l4.p1"], {"recorded": False})
    assert res.status_code == 201
    assert res.json()["evaluation_status"] == "not_evaluable"
    assert self_assess(student, res.json()["id"], {"task": 1}).status_code == 422
    recorded = attempt(student, acts["u1.l4.p2"], {"recorded": True}).json()
    assert recorded["evaluation_status"] == "pending"
    assert self_assess(student, recorded["id"], {"task": 3}).json()["score"] == 1.0


def test_closed_formats_and_other_accounts_cannot_self_assess(
    student: Account, all_formats: dict[str, Any], make_account: AccountFactory
) -> None:
    writing = all_formats["u1-l3-escritura"]["activities"]
    closed = attempt(student, writing["u1.l3.p3"], {"order": ["I", "usually", "walk", "to work"]})
    assert self_assess(student, closed.json()["id"], {"task": 1}).status_code == 422
    mine = attempt(student, writing["u1.l3.p1"], {"text": TEXT}).json()
    other = make_account("otra@example.com")
    assert self_assess(other, mine["id"], {"task": 1}).status_code == 404
    res = student.client.post(
        f"/api/v1/attempts/{mine['id']}/self-assessment", json={"scores": {"task": 1}}
    )
    assert res.status_code == 403  # sin CSRF
