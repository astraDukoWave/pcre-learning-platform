"""NFR-05 / AC-19 (parte de CS-03): cabeceras de seguridad y límite de cuerpo."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient

from tests.helpers import Account


def test_security_headers_on_every_response(client: TestClient) -> None:
    for path in ("/health", "/api/v1/no-existe"):
        res = client.get(path)
        csp = res.headers["content-security-policy"]
        for directive in (
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self'",
            "img-src 'self' data:",
            "media-src 'self' blob:",
            "font-src 'self'",
            "frame-ancestors 'none'",
            "object-src 'none'",
            "base-uri 'self'",
        ):
            assert directive in csp
        assert res.headers["x-content-type-options"] == "nosniff"
        assert res.headers["referrer-policy"] == "strict-origin-when-cross-origin"
        assert res.headers["permissions-policy"] == "microphone=(self), camera=(), geolocation=()"
        assert "strict-transport-security" not in res.headers  # solo en producción


def test_json_body_over_64kb_is_413(student: Account) -> None:
    res = student.client.patch(
        "/api/v1/me",
        content=b'{"display_name": "' + b"a" * (65 * 1024) + b'"}',
        headers={**student.headers(), "Content-Type": "application/json"},
    )
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "payload_too_large"


def test_hsts_only_in_production(container: object) -> None:
    from app.bootstrap import Container
    from app.main import create_app

    assert isinstance(container, Container)
    prod = container.settings.model_copy(
        update={"app_env": "prod", "app_origin": "https://pcre.example.com"}
    )
    container.settings = prod
    with TestClient(create_app(prod, container=container), base_url="https://testserver") as c:
        res = c.get("/health")
    assert res.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"
    assert "wss://pcre.example.com" in res.headers["content-security-policy"]


def test_engine_hides_query_parameters_in_errors(engine: object) -> None:
    assert getattr(engine, "hide_parameters", False) is True


def test_chunked_body_over_the_limit_is_413(student: Account) -> None:
    """Sin `Content-Length` (cuerpo por partes) el límite se aplica al leer."""

    def chunks() -> Iterator[bytes]:
        yield b'{"display_name": "'
        for _ in range(70):
            yield b"a" * 1024
        yield b'"}'

    res = student.client.patch(
        "/api/v1/me",
        content=chunks(),
        headers={**student.headers(), "Content-Type": "application/json"},
    )
    assert res.status_code == 413
