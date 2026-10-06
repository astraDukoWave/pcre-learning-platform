#!/usr/bin/env bash
# Drift del contrato (REQ-02, job `contract`; NFR-13): el OpenAPI exportado del código debe
# ser igual a docs/api/openapi.json y los tipos regenerados iguales a src/api/schema.d.ts.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

(cd "$ROOT/apps/backend" && uv run --locked python ../../scripts/openapi/export.py --out "$TMP/openapi.json" >/dev/null)
if ! diff -u "$ROOT/docs/api/openapi.json" "$TMP/openapi.json"; then
  echo "docs/api/openapi.json no coincide con el código: corre 'make openapi' y commitea." >&2
  exit 1
fi
(cd "$ROOT/apps/frontend" && npx openapi-typescript ../../docs/api/openapi.json -o "$TMP/schema.d.ts" >/dev/null 2>&1)
if ! diff -u "$ROOT/apps/frontend/src/api/schema.d.ts" "$TMP/schema.d.ts"; then
  echo "src/api/schema.d.ts no coincide con el OpenAPI: corre 'make openapi' y commitea." >&2
  exit 1
fi
echo "contrato OK: OpenAPI y tipos sin diferencias"
