from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.core.logging import FORBIDDEN_KEYS, JsonFormatter, request_id_var, user_ref


def _format(**extra: object) -> dict[str, object]:
    record = logging.LogRecord("app.test", logging.INFO, __file__, 1, "evento", None, None)
    for key, value in extra.items():
        setattr(record, key, value)
    return json.loads(JsonFormatter().format(record))  # type: ignore[no-any-return]


def test_log_line_has_the_required_shape() -> None:
    token = request_id_var.set("req-123456")
    try:
        line = _format(route="/api/v1/x", status=200, duration_ms=1.5, user_ref="abc")
    finally:
        request_id_var.reset(token)
    assert line["msg"] == "evento"
    assert line["level"] == "info"
    assert line["request_id"] == "req-123456"
    assert {"ts", "route", "status", "duration_ms", "user_ref"} <= line.keys()


@pytest.mark.parametrize("key", sorted(FORBIDDEN_KEYS))
def test_forbidden_fields_never_reach_the_log(key: str) -> None:
    line = _format(**{key: "valor-sensible"}, nested={key: "valor-sensible", "ok": 1})
    raw = json.dumps(line)
    assert "valor-sensible" not in raw
    assert line["nested"] == {"ok": 1}


def test_access_log_has_no_sensitive_headers(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="app.access"):
        client.get(
            "/health",
            headers={"Authorization": "Bearer top-secret", "Cookie": "__Host-pcre_session=abc"},
        )
    formatted = [JsonFormatter().format(r) for r in caplog.records if r.name == "app.access"]
    assert formatted, "se esperaba una línea de acceso"
    for line in formatted:
        assert "top-secret" not in line
        assert "pcre_session" not in line
    access = json.loads(formatted[-1])
    assert access["route"] == "/health"
    assert access["status"] == 200


def test_user_ref_is_salted_and_stable() -> None:
    a = user_ref("1b4e28ba-2fa1-11d2-883f-0016d3cca427", "s1")
    assert a == user_ref("1b4e28ba-2fa1-11d2-883f-0016d3cca427", "s1")
    assert a != user_ref("1b4e28ba-2fa1-11d2-883f-0016d3cca427", "s2")
    assert len(a) == 12
