# PCRE Learning Platform — comandos de desarrollo (AGENTS.md, "Comandos").
# `make verify` es el check previo a un PR: tras `make setup` no necesita red ni llaves.
SHELL := /bin/bash
.DEFAULT_GOAL := help

-include .env

BACKEND := apps/backend
DB_HOST ?= 127.0.0.1:5432
export DATABASE_URL ?= postgresql+psycopg://pcre:pcre@$(DB_HOST)/pcre
TEST_DATABASE_URL ?= postgresql+psycopg://pcre:pcre@$(DB_HOST)/pcre_test
MIGCHECK_DATABASE_URL ?= postgresql+psycopg://pcre:pcre@$(DB_HOST)/pcre_migcheck
UV_RUN := cd $(BACKEND) && uv run --locked

.PHONY: help setup db-up db-reset migrate dev test lint typecheck migrations-check verify

help:
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-18s %s\n", $$1, $$2}'

setup: ## Instala dependencias (uv sync; npm ci cuando exista el frontend)
	cd $(BACKEND) && uv sync --locked

db-up: ## Arranca PostgreSQL y crea rol y bases (idempotente)
	scripts/dev/db.sh up

db-reset: ## Vacía la base de desarrollo y la migra a head
	scripts/dev/db.sh reset

migrate: ## alembic upgrade head sobre DATABASE_URL
	$(UV_RUN) alembic upgrade head

dev: ## Backend con recarga en :8000
	$(UV_RUN) uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

test: ## pytest contra PostgreSQL (sin red ni llaves)
	$(UV_RUN) env DATABASE_URL=$(TEST_DATABASE_URL) APP_ENV=test pytest

lint: ## ruff (check y format), import-linter y actionlint
	$(UV_RUN) ruff check .
	$(UV_RUN) ruff format --check .
	$(UV_RUN) lint-imports
	$(UV_RUN) actionlint -no-color ../../.github/workflows/*.yml

typecheck: ## mypy estricto
	$(UV_RUN) mypy app tests import_contracts.py

migrations-check: ## Migraciones: vacía→head, legado→head, alembic check, downgrade/upgrade
	DATABASE_URL=$(MIGCHECK_DATABASE_URL) scripts/dev/migrations-check.sh

verify: lint typecheck test migrations-check ## Todo lo anterior: el check previo a un PR
	@echo "make verify: OK"
