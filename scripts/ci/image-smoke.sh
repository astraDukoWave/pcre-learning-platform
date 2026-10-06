#!/usr/bin/env bash
# Job `image` (REQ-02, AC-17, AC-18): construye la imagen, migra dentro de ella con el
# comando `release` de heroku.yml y la arranca con `run.web`, junto a PostgreSQL 16.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TAG="${IMAGE_TAG:-pcre:ci}"
NET="pcre-ci-net"
PORT="${SMOKE_PORT:-8099}"
DB_URL="postgresql://pcre:pcre@pcre-ci-db:5432/pcre"

cleanup() {
  docker rm -f pcre-ci-app pcre-ci-db >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup

cd "$ROOT"
WEB_CMD="$(cd apps/backend && uv run --locked python ../../scripts/ci/heroku_cmd.py web)"
RELEASE_CMD="$(cd apps/backend && uv run --locked python ../../scripts/ci/heroku_cmd.py release)"
echo "run.web: $WEB_CMD"
echo "release: $RELEASE_CMD"

if [ "${SKIP_BUILD:-0}" != "1" ]; then
  docker build -t "$TAG" .
fi

docker network create "$NET" >/dev/null
docker run -d --name pcre-ci-db --network "$NET" \
  -e POSTGRES_USER=pcre -e POSTGRES_PASSWORD=pcre -e POSTGRES_DB=pcre postgres:16 >/dev/null
for _ in $(seq 1 60); do
  docker exec pcre-ci-db pg_isready -U pcre -d pcre >/dev/null 2>&1 && break
  sleep 1
done

APP_ENV_ARGS=(-e "DATABASE_URL=$DB_URL" -e APP_ENV=prod -e "APP_ORIGIN=http://localhost:$PORT" -e LOG_SALT=ci-smoke)
docker run --rm --network "$NET" "${APP_ENV_ARGS[@]}" "$TAG" sh -c "$RELEASE_CMD"
docker run -d --name pcre-ci-app --network "$NET" -p "127.0.0.1:$PORT:$PORT" \
  "${APP_ENV_ARGS[@]}" -e "PORT=$PORT" "$TAG" sh -c "$WEB_CMD" >/dev/null

BASE="http://127.0.0.1:$PORT"
for _ in $(seq 1 60); do
  curl -fsS "$BASE/health" >/dev/null 2>&1 && break
  sleep 1
done

fail() { echo "SONDA FALLIDA: $*" >&2; docker logs pcre-ci-app >&2 || true; exit 1; }
check_status() {  # url, accept, esperado
  local code
  code="$(curl -s -o /tmp/pcre-smoke-body -w '%{http_code}' -H "Accept: $2" "$BASE$1")"
  [ "$code" = "$3" ] || fail "$1 devolvió $code (esperado $3): $(head -c 300 /tmp/pcre-smoke-body)"
}

check_status /health application/json 200
grep -q '"status":"ok"' /tmp/pcre-smoke-body || fail "/health sin status ok"
check_status /api/v1/ready application/json 200
grep -q '"status":"ready"' /tmp/pcre-smoke-body || fail "/api/v1/ready sin status ready"
check_status / text/html 200
grep -q '<div id="root">' /tmp/pcre-smoke-body || fail "/ no sirve el root de la SPA"
check_status /api/v1/no-existe text/html 404
grep -q '"code":"not_found"' /tmp/pcre-smoke-body || fail "/api/v1/no-existe no es JSON"
check_status /assets/no-existe.js '*/*' 404
if grep -q '<div id="root">' /tmp/pcre-smoke-body; then fail "un asset inexistente devolvió index.html"; fi
echo "sondas OK: /health, /api/v1/ready, /, /api/v1/no-existe (404 JSON), asset inexistente (404)"

rm -rf /tmp/pcre-dist && mkdir -p /tmp/pcre-dist
docker cp pcre-ci-app:/srv/frontend/dist/. /tmp/pcre-dist/
"$ROOT/scripts/ci/bundle-grep.sh" /tmp/pcre-dist
