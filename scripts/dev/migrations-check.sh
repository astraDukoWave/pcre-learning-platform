#!/usr/bin/env bash
# Chequeo de migraciones (REQ-02, job `migrations`; AC-03) contra una base DESECHABLE:
#   1. base vacía → head + `alembic check`
#   2. esquema legado (816c80672425) + seed legado → head + `alembic check`, sin perder filas
#   3. downgrade y upgrade de cada migración nueva (posterior a 816c80672425)
# Requiere DATABASE_URL apuntando a la base desechable (por defecto `pcre_migcheck`).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LEGACY_HEAD="816c80672425"
cd "$ROOT/apps/backend"

case "${DATABASE_URL:-}" in
  *pcre_migcheck*|*migcheck*) ;;
  *) echo "DATABASE_URL debe apuntar a una base desechable (*migcheck*)" >&2; exit 2 ;;
esac

dbtool() { uv run python ../../scripts/dev/dbtool.py "$@"; }
current() { uv run alembic current 2>/dev/null | awk '{print $1}' | head -n1; }

echo "== 1. Base vacía → head"
dbtool reset
uv run alembic upgrade head
uv run alembic check

echo "== 2. Esquema legado con seed → head"
dbtool reset
uv run alembic upgrade "$LEGACY_HEAD"
dbtool load-sql tests/fixtures/legacy_seed.sql
before_questions="$(dbtool count questions)"
before_users="$(dbtool count users)"
uv run alembic upgrade head
uv run alembic check
after_questions="$(dbtool count questions)"
after_users="$(dbtool count users)"
if [ "$before_questions" != "$after_questions" ] || [ "$before_users" != "$after_users" ]; then
  echo "Se perdieron filas legadas: questions $before_questions→$after_questions, users $before_users→$after_users" >&2
  exit 1
fi
echo "filas legadas intactas: questions=$after_questions users=$after_users"

echo "== 3. Downgrade y upgrade de cada migración nueva"
steps=0
while [ "$(current)" != "$LEGACY_HEAD" ]; do
  rev="$(current)"
  uv run alembic downgrade -1
  echo "downgrade de $rev ok"
  steps=$((steps + 1))
  if [ "$steps" -gt 100 ]; then echo "demasiadas migraciones" >&2; exit 1; fi
done
uv run alembic upgrade head
uv run alembic check
echo "migraciones nuevas probadas: $steps"
echo "OK: chequeo de migraciones completo"
