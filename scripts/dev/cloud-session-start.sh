#!/usr/bin/env bash
# Hook SessionStart de Claude Code (startup|resume). Solo actúa en la nube
# (CLAUDE_CODE_REMOTE=true): PostgreSQL, rol y bases, `uv sync` y `npm ci` si cambió el
# lockfile. Imprime un resumen y SIEMPRE sale con 0; las fallas quedan a la vista.
set -u

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
summary=()
note() { summary+=("$1"); }

if "$ROOT/scripts/dev/db.sh" up >/tmp/pcre-db-up.log 2>&1; then
  note "ok    PostgreSQL y bases pcre, pcre_test, pcre_migcheck"
else
  note "FALLA PostgreSQL (ver /tmp/pcre-db-up.log)"
fi

if (cd "$ROOT/apps/backend" && uv sync --locked >/tmp/pcre-uv-sync.log 2>&1); then
  note "ok    uv sync (apps/backend)"
else
  note "FALLA uv sync (ver /tmp/pcre-uv-sync.log)"
fi

LOCK="$ROOT/apps/frontend/package-lock.json"
if [ -f "$LOCK" ]; then
  stamp="$ROOT/apps/frontend/node_modules/.pcre-lock-sha256"
  want="$(sha256sum "$LOCK" | cut -d' ' -f1)"
  if [ -f "$stamp" ] && [ "$(cat "$stamp")" = "$want" ]; then
    note "ok    npm ci (lockfile sin cambios)"
  elif (cd "$ROOT/apps/frontend" && npm ci --no-audit --no-fund >/tmp/pcre-npm-ci.log 2>&1); then
    echo "$want" >"$stamp"
    note "ok    npm ci (apps/frontend)"
  else
    note "FALLA npm ci (ver /tmp/pcre-npm-ci.log)"
  fi
fi

echo "== PCRE · arranque de la sesión cloud"
for line in "${summary[@]}"; do echo "  $line"; done
echo "  siguiente: make verify"
exit 0
