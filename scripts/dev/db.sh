#!/usr/bin/env bash
# PostgreSQL local para desarrollo: `up` arranca y crea rol y bases (idempotente);
# `reset` vacía la base de desarrollo y la migra a head.
# En la sesión cloud (CLAUDE_CODE_REMOTE=true) usa el PostgreSQL 16 de la VM; fuera de
# ella, el servicio `db` de docker-compose.yml (Codespaces o tu máquina).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DBS=(pcre pcre_test pcre_migcheck)

as_postgres() {
  if [ "$(id -u)" = "0" ]; then
    runuser -u postgres -- "$@"
  else
    sudo -n -u postgres "$@"
  fi
}

use_docker() {
  [ "${CLAUDE_CODE_REMOTE:-}" != "true" ] && command -v docker >/dev/null 2>&1 \
    && docker compose version >/dev/null 2>&1 && ! command -v pg_ctlcluster >/dev/null 2>&1
}

start_local() {
  if ! pg_isready -q -h 127.0.0.1; then
    service postgresql start >/dev/null 2>&1 || sudo -n service postgresql start >/dev/null 2>&1 || true
  fi
  for _ in $(seq 1 30); do
    pg_isready -q -h 127.0.0.1 && return 0
    sleep 1
  done
  echo "PostgreSQL no respondió en 127.0.0.1:5432" >&2
  return 1
}

ensure_local_dbs() {
  as_postgres psql -v ON_ERROR_STOP=1 -qtAc \
    "DO \$\$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'pcre') THEN CREATE ROLE pcre LOGIN PASSWORD 'pcre' CREATEDB; END IF; END \$\$;"
  for db in "${DBS[@]}"; do
    if [ "$(as_postgres psql -qtAc "SELECT 1 FROM pg_database WHERE datname = '${db}'")" != "1" ]; then
      as_postgres psql -v ON_ERROR_STOP=1 -qtAc "CREATE DATABASE ${db} OWNER pcre"
    fi
  done
}

up_docker() {
  (cd "$ROOT" && docker compose up -d --wait db)
  for db in pcre_test pcre_migcheck; do
    (cd "$ROOT" && docker compose exec -T db psql -U pcre -d pcre -qtAc \
      "SELECT 1 FROM pg_database WHERE datname = '${db}'" | grep -q 1) \
      || (cd "$ROOT" && docker compose exec -T db psql -U pcre -d pcre -qc "CREATE DATABASE ${db}")
  done
}

case "${1:-up}" in
  up)
    if use_docker; then up_docker; else start_local && ensure_local_dbs; fi
    echo "PostgreSQL listo: bases ${DBS[*]} (rol pcre)"
    ;;
  reset)
    cd "$ROOT/apps/backend"
    uv run python ../../scripts/dev/dbtool.py reset
    uv run alembic upgrade head
    ;;
  *)
    echo "uso: $0 [up|reset]" >&2
    exit 2
    ;;
esac
