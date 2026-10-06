from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.http.health import expected_migration_head


def test_health_is_ok_without_database(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
    assert len(res.headers["x-request-id"]) >= 8


def test_request_id_is_echoed_when_valid(client: TestClient) -> None:
    res = client.get("/health", headers={"X-Request-ID": "abc12345-req"})
    assert res.headers["x-request-id"] == "abc12345-req"
    res = client.get("/health", headers={"X-Request-ID": "bad id with spaces"})
    assert res.headers["x-request-id"] != "bad id with spaces"


def test_ready_reports_expected_head(client: TestClient) -> None:
    res = client.get("/api/v1/ready")
    assert res.status_code == 200
    assert res.json() == {"status": "ready", "migration": expected_migration_head()}


def test_ready_fails_when_migration_differs(client: TestClient, db: Session) -> None:
    db.execute(text("UPDATE alembic_version SET version_num = 'bc0bb9a48e10'"))
    db.commit()
    res = client.get("/api/v1/ready")
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "migration_mismatch"


def test_unknown_api_route_is_json_404(client: TestClient) -> None:
    res = client.get("/api/v1/no-existe")
    assert res.status_code == 404
    body = res.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["request_id"] == res.headers["x-request-id"]


def test_unexpected_error_returns_envelope_with_request_id(app: FastAPI) -> None:
    def _boom() -> None:
        raise RuntimeError("secreto que no debe salir")

    app.router.add_api_route("/api/v1/_boom", _boom)
    app.router.routes.insert(0, app.router.routes.pop())  # antes del fallback de la SPA
    with TestClient(app, base_url="https://testserver") as c:
        res = c.get("/api/v1/_boom")
    assert res.status_code == 500
    body = res.json()
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["request_id"] == res.headers["x-request-id"]
    assert "secreto" not in res.text


def test_legacy_endpoints_are_gone(client: TestClient) -> None:
    assert client.get("/api/v1/courses").status_code == 404
