"""Archivos del frontend y del audio, con fallback estricto de la SPA (§6.2).

- `/assets/*`: build con hash de Vite, caché inmutable. Un asset inexistente es 404.
- `/media/*`: audio del contenido (`MEDIA_DIR`).
- Fallback a `index.html` solo para `GET` con `Accept: text/html` fuera de `/api`, `/ws`,
  `/media`, `/assets` y `/health`. Un 404 de la API es JSON, nunca `index.html`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import FileResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from app.core.config import Settings
from app.core.errors import NotFound

EXCLUDED_PREFIXES = frozenset({"api", "ws", "media", "assets", "health"})
IMMUTABLE = "public, max-age=31536000, immutable"
MEDIA_CACHE = "public, max-age=86400"


class _CachedStaticFiles(StaticFiles):
    def __init__(self, *, directory: Path, cache_control: str) -> None:
        super().__init__(directory=directory, check_dir=False)
        self._cache_control = cache_control
        self._directory = directory

    async def get_response(self, path: str, scope: Scope) -> Response:
        if not self._directory.is_dir():
            raise NotFound()
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = self._cache_control
        return response

    def file_response(self, *args: Any, **kwargs: Any) -> Response:
        return super().file_response(*args, **kwargs)


def mount_frontend(app: FastAPI, settings: Settings) -> None:
    dist = settings.frontend_dist
    app.mount(
        "/assets",
        _CachedStaticFiles(directory=dist / "assets", cache_control=IMMUTABLE),
        name="assets",
    )
    app.mount(
        "/media",
        _CachedStaticFiles(directory=settings.media_dir, cache_control=MEDIA_CACHE),
        name="media",
    )
    app.include_router(_spa_router(dist))


def _spa_router(dist: Path) -> APIRouter:
    router = APIRouter(include_in_schema=False)

    @router.api_route("/{full_path:path}", methods=["GET", "HEAD"])
    def spa(full_path: str, request: Request) -> FileResponse:
        first = full_path.split("/", 1)[0]
        if first in EXCLUDED_PREFIXES or ".." in full_path.split("/"):
            raise NotFound()
        if full_path and "/" not in full_path and full_path != "index.html":
            candidate = dist / full_path
            if candidate.is_file():
                return FileResponse(candidate, headers={"Cache-Control": MEDIA_CACHE})
        if "text/html" not in request.headers.get("accept", ""):
            raise NotFound()
        index = dist / "index.html"
        if not index.is_file():
            raise NotFound("El frontend no está compilado.", code="frontend_not_built")
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    @router.api_route("/{full_path:path}", methods=["POST", "PUT", "PATCH", "DELETE"])
    def unknown(full_path: str) -> None:
        raise NotFound()

    return router
