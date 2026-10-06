# PCRE Learning Platform — comandos de desarrollo (AGENTS.md, "Comandos").
# `make verify` es el check previo a un PR: tras `make setup` no necesita red ni llaves.
SHELL := /bin/bash
.DEFAULT_GOAL := help

-include .env

BACKEND := apps/backend
FRONTEND := apps/frontend
DB_HOST ?= 127.0.0.1:5432
export DATABASE_URL ?= postgresql+psycopg://pcre:pcre@$(DB_HOST)/pcre
TEST_DATABASE_URL ?= postgresql+psycopg://pcre:pcre@$(DB_HOST)/pcre_test
MIGCHECK_DATABASE_URL ?= postgresql+psycopg://pcre:pcre@$(DB_HOST)/pcre_migcheck
UV_RUN := cd $(BACKEND) && uv run --locked

.PHONY: help setup db-up db-reset migrate dev dev-backend dev-frontend test lint typecheck migrations-check openapi frontend-check contract-check content-lint review-packet content-import e2e verify

help:
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-18s %s\n", $$1, $$2}'

setup: ## Instala dependencias (uv sync y npm ci)
	cd $(BACKEND) && uv sync --locked
	cd $(FRONTEND) && npm ci --no-audit --no-fund

db-up: ## Arranca PostgreSQL y crea rol y bases (idempotente)
	scripts/dev/db.sh up

db-reset: ## Vacía la base de desarrollo y la migra a head
	scripts/dev/db.sh reset

migrate: ## alembic upgrade head sobre DATABASE_URL
	$(UV_RUN) alembic upgrade head

dev: ## Backend :8000 + Vite :5173 (proxy de /api, /ws y /media)
	$(MAKE) -j2 dev-backend dev-frontend

dev-backend:
	$(UV_RUN) uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

dev-frontend:
	cd $(FRONTEND) && npm run dev

test: ## pytest contra PostgreSQL (sin red ni llaves)
	$(UV_RUN) env DATABASE_URL=$(TEST_DATABASE_URL) APP_ENV=test pytest

lint: ## ruff (check y format), import-linter y actionlint
	$(UV_RUN) ruff check . ../../e2e ../../scripts ../../evals
	$(UV_RUN) ruff format --check . ../../e2e ../../scripts ../../evals
	$(UV_RUN) lint-imports
	$(UV_RUN) actionlint -no-color ../../.github/workflows/*.yml

typecheck: ## mypy estricto
	$(UV_RUN) mypy app tests import_contracts.py ../../scripts/openapi/export.py ../../scripts/ci/heroku_cmd.py ../../scripts/content/generate_audio.py ../../scripts/content/review_packet.py ../../scripts/perf/smoke.py ../../evals/run.py

migrations-check: ## Migraciones: vacía→head, legado→head, alembic check, downgrade/upgrade
	DATABASE_URL=$(MIGCHECK_DATABASE_URL) scripts/dev/migrations-check.sh

openapi: ## Exporta docs/api/openapi.json y regenera los tipos del frontend
	$(UV_RUN) python ../../scripts/openapi/export.py
	cd $(FRONTEND) && npm run gen:api

frontend-check: ## Frontend: typecheck, ESLint, Vitest y build
	cd $(FRONTEND) && npm run typecheck && npm run lint && npm test && npm run build

contract-check: ## OpenAPI y tipos sin diferencias con el código
	scripts/ci/contract-check.sh

content-lint: ## Lint del contenido; regenera docs/contenido/cobertura.md y los paquetes de revisión
	$(UV_RUN) python -m app.cli content lint --dir ../../content --coverage ../../docs/contenido/cobertura.md
	$(UV_RUN) python ../../scripts/content/review_packet.py --all

review-packet: ## Paquete de revisión: make review-packet UNIT=u1 (u1 … u8, inicial o final)
	@test -n "$(UNIT)" || { echo "uso: make review-packet UNIT=u1"; exit 2; }
	$(UV_RUN) python ../../scripts/content/review_packet.py --unit $(UNIT)

content-import: ## Importa borradores a DATABASE_URL (nunca aprueba ni publica)
	$(UV_RUN) python -m app.cli content import --dir ../../content

e2e: ## E2E con Playwright contra el build servido por FastAPI (en la CI; local con Chromium)
	cd $(FRONTEND) && npm run build
	$(UV_RUN) --group e2e pytest ../../e2e -p no:cacheprovider

verify: lint typecheck test migrations-check content-lint frontend-check contract-check ## Todo lo anterior: el check previo a un PR
	@echo "make verify: OK"
