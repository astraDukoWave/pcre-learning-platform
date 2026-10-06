#!/usr/bin/env bash
# AC-18: el bundle del frontend no contiene llaves ni hosts de proveedores.
# Uso: scripts/ci/bundle-grep.sh <directorio dist>
set -euo pipefail
DIST="${1:?directorio del bundle}"
PATTERN='deepgram\.com|googleapis\.com|generativelanguage|api\.openai\.com|anthropic\.com|herokuapp\.com/api|DEEPGRAM_API_KEY|GEMINI_API_KEY|HEROKU_API_KEY|AIza[0-9A-Za-z_-]{35}|sk-[A-Za-z0-9]{32,}|-----BEGIN [A-Z ]*PRIVATE KEY'
if grep -rEIl "$PATTERN" "$DIST"; then
  echo "El bundle contiene llaves u hosts de proveedores (ver archivos arriba)." >&2
  exit 1
fi
echo "bundle limpio: sin llaves ni hosts de proveedores en $DIST"
