"""AC-07: CSRF y Origin en métodos no seguros."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.helpers import Account


@pytest.mark.parametrize(
    ("method", "url", "body"),
    [
        ("post", "/api/v1/auth/logout", None),
        ("patch", "/api/v1/me", {"display_name": "X"}),
        ("delete", "/api/v1/me", {"password": "correct horse battery"}),
    ],
)
def test_unsafe_method_without_or_with_wrong_token_is_403(
    student: Account, method: str, url: str, body: dict[str, str] | None
) -> None:
    send = getattr(student.client, method) if method != "delete" else None
    for headers in ({}, {"X-CSRF-Token": "token-incorrecto"}):
        if method == "delete":
            res = student.client.request("DELETE", url, json=body, headers=headers)
        else:
            res = send(url, json=body, headers=headers)  # type: ignore[misc]
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "csrf_invalid"
        assert res.json()["error"]["message"] == "Recarga la página para continuar."
    assert student.client.get("/api/v1/me").status_code == 200  # la sesión sigue viva


def test_foreign_or_missing_origin_is_403(student: Account) -> None:
    res = student.client.patch(
        "/api/v1/me",
        json={"display_name": "X"},
        headers={**student.headers(), "Origin": "https://evil.example.com"},
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "origin_invalid"
    bare = TestClient(student.client.app, base_url="https://testserver")
    res = bare.post("/api/v1/auth/login", json={"email": student.email, "password": "x" * 12})
    assert res.status_code == 403


def test_referer_is_accepted_when_origin_is_missing(student: Account) -> None:
    bare = TestClient(student.client.app, base_url="https://testserver")
    res = bare.post(
        "/api/v1/auth/login",
        json={"email": student.email, "password": student.password},
        headers={"Referer": "http://localhost:5173/entrar"},
    )
    assert res.status_code == 200


def test_valid_token_and_origin_pass(student: Account) -> None:
    res = student.client.patch(
        "/api/v1/me", json={"display_name": "Ana"}, headers=student.headers()
    )
    assert res.status_code == 200
    assert res.json()["display_name"] == "Ana"


def test_safe_methods_need_no_token(student: Account) -> None:
    assert (
        student.client.get("/api/v1/me", headers={"Origin": "https://evil.example.com"}).status_code
        == 200
    )
