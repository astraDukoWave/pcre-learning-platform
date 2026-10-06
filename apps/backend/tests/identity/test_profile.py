"""REQ-05: perfil y meta con lista explícita de campos."""

from __future__ import annotations

from tests.helpers import Account


def test_me_returns_profile_and_csrf(student: Account) -> None:
    me = student.client.get("/api/v1/me").json()
    assert me["email"] == student.email
    assert me["role"] == "student"
    assert me["timezone"] == "America/Mexico_City"
    assert me["csrf_token"] == student.csrf


def test_onboarding_goal_is_saved(student: Account) -> None:
    body = {
        "goal_purpose": "studies",
        "target_exam": "other",
        "target_exam_other": "Examen de mi universidad",
        "target_score": "B2",
        "target_date": "2027-03-01",
        "self_reported_level": "unknown",
        "timezone": "America/Bogota",
        "onboarded": True,
    }
    res = student.client.patch("/api/v1/me", json=body, headers=student.headers())
    assert res.status_code == 200, res.text
    me = res.json()
    assert me["onboarded"] is True
    assert me["target_exam_other"] == "Examen de mi universidad"
    assert me["timezone"] == "America/Bogota"
    res = student.client.patch(
        "/api/v1/me", json={"target_exam": "toefl_ibt"}, headers=student.headers()
    )
    assert res.json()["target_exam_other"] is None


def test_unknown_is_a_valid_answer(student: Account) -> None:
    res = student.client.patch(
        "/api/v1/me",
        json={
            "goal_purpose": "unknown",
            "target_exam": "unknown",
            "self_reported_level": "unknown",
        },
        headers=student.headers(),
    )
    assert res.status_code == 200


def test_role_and_email_are_not_editable(student: Account) -> None:
    for body in (
        {"role": "admin"},
        {"email": "otra@example.com"},
        {"is_internal": True},
        {"user_id": "x"},
    ):
        res = student.client.patch("/api/v1/me", json=body, headers=student.headers())
        assert res.status_code == 422, body
    assert student.client.get("/api/v1/me").json()["role"] == "student"


def test_invalid_timezone_and_level(student: Account) -> None:
    res = student.client.patch(
        "/api/v1/me", json={"timezone": "Marte/Base"}, headers=student.headers()
    )
    assert res.status_code == 422 and res.json()["error"]["code"] == "timezone_invalid"
    res = student.client.patch(
        "/api/v1/me", json={"self_reported_level": "C2"}, headers=student.headers()
    )
    assert res.status_code == 422
