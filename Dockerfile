# syntax=docker/dockerfile:1
# Imagen de producción (ADR-13): Node 22 compila el frontend; Python 3.12 ejecuta el
# backend con uv (sin dependencias de desarrollo) y usuario no root. Sin CMD: el arranque
# vive en heroku.yml (run.web) y la CI arranca exactamente ese comando.

FROM node:22-slim AS frontend
WORKDIR /build/apps/frontend
COPY apps/frontend/package.json apps/frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/frontend/ ./
COPY docs/api/openapi.json /build/docs/api/openapi.json
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/srv/venv \
    PATH="/srv/venv/bin:${PATH}"
# curl: Heroku lo necesita para transmitir los logs de la release phase (D1).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir "uv==0.8.17"

WORKDIR /srv/backend
COPY apps/backend/pyproject.toml apps/backend/uv.lock apps/backend/.python-version ./
RUN uv sync --locked --no-dev --no-install-project
COPY apps/backend/alembic.ini ./
COPY apps/backend/alembic ./alembic
COPY apps/backend/app ./app
COPY --from=frontend /build/apps/frontend/dist /srv/frontend/dist
COPY content /srv/content

ENV CONTENT_DIR=/srv/content \
    MEDIA_DIR=/srv/content/toefl-ibt-2026-b1-b2/audio \
    FRONTEND_DIST=/srv/frontend/dist

RUN useradd --create-home --uid 10001 pcre
USER pcre
