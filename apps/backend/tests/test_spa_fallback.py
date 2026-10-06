"""Estáticos y fallback estricto de la SPA (§6.2; AC-17 en el job `image`)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.bootstrap import Container
from app.main import create_app

HTML = {"Accept": "text/html,application/xhtml+xml"}


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text('<!doctype html><div id="root"></div>')
    (root / "assets" / "index-abc123.js").write_text("console.log('ok')")
    (root / "favicon.svg").write_text("<svg/>")
    return root


@pytest.fixture
def media(tmp_path: Path) -> Path:
    root = tmp_path / "media"
    root.mkdir()
    (root / "0a1b2c3d-anuncio.mp3").write_bytes(b"ID3fake")
    return root


@pytest.fixture
def spa(container: Container, dist: Path, media: Path) -> Iterator[TestClient]:
    settings = container.settings.model_copy(update={"frontend_dist": dist, "media_dir": media})
    container.settings = settings
    app = create_app(settings, container=container)
    origin = {"Origin": "http://localhost:5173"}
    with TestClient(app, base_url="https://testserver", headers=origin) as client:
        yield client


@pytest.mark.parametrize("path", ["/", "/ruta", "/lecciones/abc/1", "/entrar?next=%2F"])
def test_client_routes_serve_index(spa: TestClient, path: str) -> None:
    res = spa.get(path, headers=HTML)
    assert res.status_code == 200
    assert 'id="root"' in res.text
    assert res.headers["cache-control"] == "no-cache"


def test_assets_are_immutable(spa: TestClient) -> None:
    res = spa.get("/assets/index-abc123.js")
    assert res.status_code == 200
    assert "immutable" in res.headers["cache-control"]


@pytest.mark.parametrize(
    "path", ["/assets/missing.js", "/assets/%2e%2e/%2e%2e/etc/passwd", "/media/missing.mp3"]
)
def test_missing_static_is_404_never_index(spa: TestClient, path: str) -> None:
    res = spa.get(path, headers=HTML)
    assert res.status_code == 404
    assert 'id="root"' not in res.text


def test_media_is_served(spa: TestClient) -> None:
    res = spa.get("/media/0a1b2c3d-anuncio.mp3")
    assert res.status_code == 200
    assert res.headers["content-type"] == "audio/mpeg"


@pytest.mark.parametrize("path", ["/api/v1/no-existe", "/api", "/ws/voice/x", "/health/x"])
def test_reserved_prefixes_never_fall_back(spa: TestClient, path: str) -> None:
    res = spa.get(path, headers=HTML)
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "not_found"


def test_non_html_requests_get_json_404(spa: TestClient) -> None:
    res = spa.get("/ruta", headers={"Accept": "application/json"})
    assert res.status_code == 404
    assert res.headers["content-type"].startswith("application/json")


def test_unsafe_methods_on_unknown_paths_are_404(spa: TestClient) -> None:
    assert spa.post("/ruta", json={}).status_code == 404
    assert spa.delete("/api/v1/no-existe").status_code == 404


def test_root_files_are_served(spa: TestClient) -> None:
    res = spa.get("/favicon.svg")
    assert res.status_code == 200


def test_health_wins_over_fallback(spa: TestClient) -> None:
    assert spa.get("/health", headers=HTML).json() == {"status": "ok"}


def test_without_build_the_fallback_says_so(container: Container, tmp_path: Path) -> None:
    settings = container.settings.model_copy(update={"frontend_dist": tmp_path / "sin-build"})
    container.settings = settings
    with TestClient(create_app(settings, container=container), base_url="https://testserver") as c:
        res = c.get("/una-pagina", headers=HTML)
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "frontend_not_built"
