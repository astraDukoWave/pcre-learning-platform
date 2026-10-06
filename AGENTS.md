# AGENTS.md

Guía para cualquier agente de código (Claude Code, Cursor, Codex) que
trabaje en este repo. Las reglas propias del agente autónomo de Claude están
en `CLAUDE.md`; el estado vive en `HANDOFF.md` y `STATE.md`.

## Qué es

PCRE Learning Platform: SaaS de práctica de inglés B1 → B2 para
hispanohablantes, con una primera ruta tipo TOEFL iBT (formato 2026).
Monolito modular: FastAPI + PostgreSQL en `apps/backend/`, React + Vite +
TypeScript en `apps/frontend/`, contenido como código en `content/`,
despliegue en Heroku (stack container) con `Dockerfile` y `heroku.yml` en
la raíz.

Documentos que mandan, en este orden: `docs/specs/` (qué se construye),
`docs/plans/` (cómo y en qué orden), `docs/arquitectura.md` (decisiones
técnicas y ADRs) y `docs/contenido/contrato-curricular.md` (reglas del
contenido).

## Estado del código

MVP-01 en curso (ver `STATE.md`). Desde CS-01 el backend usa Python 3.12 con `uv`,
pytest contra PostgreSQL real, ruff, mypy e import-linter; la CI corre en cada PR y
`ci-gate` es el check que importa. El prototipo de la fase 1 se retiró (sus tablas
siguen congeladas en `app/modules/legacy/models.py`).

## Comandos

```bash
make setup             # uv sync (+ npm ci desde CS-02)
make db-up             # PostgreSQL local: VM cloud (service) o docker compose (db)
make migrate           # alembic upgrade head sobre DATABASE_URL (base pcre)
make dev               # backend con recarga en :8000
make test              # pytest contra pcre_test (sin red: pytest-socket)
make lint              # ruff check + format, import-linter y actionlint
make typecheck         # mypy estricto
make migrations-check  # vacía→head, legado+seed→head, alembic check, downgrade/upgrade
make openapi           # docs/api/openapi.json + apps/frontend/src/api/schema.d.ts
make frontend-check    # tsc, ESLint, Vitest y build del frontend
make contract-check    # OpenAPI y tipos sin diferencias con el código
make content-lint      # lint del contenido + docs/contenido/cobertura.md
make content-import    # importa borradores a DATABASE_URL (nunca aprueba ni publica)
make verify            # todo lo anterior: el check previo a un PR
```

`make e2e` (Playwright en Python) corre en la CI; en la sesión cloud, con
`PW_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome`.
`python -m app.cli dev-seed` (solo dev/test) crea cuentas de prueba y publica el contenido
con el revisor `fixture:dev`. La release phase de Heroku corre
`python -m app.cli release` (migración + importación de `CONTENT_DIR`). La imagen de
producción se prueba con `scripts/ci/image-smoke.sh` (job `image`; necesita Docker y
acceso a los repositorios de Debian). En la sesión cloud, el hook `SessionStart`
(`scripts/dev/cloud-session-start.sh`) arranca PostgreSQL, crea el rol `pcre` y las bases
`pcre`, `pcre_test` y `pcre_migcheck`, y corre `uv sync`. Fuera de la nube, `make db-up`
usa `docker-compose.yml` (solo el servicio `db`).

## Reglas de arquitectura (no violar)

1. Backend por módulos (`app/modules/<módulo>/`) con capas `domain`,
   `service`, `ports`, `models`, `repository`, `schemas`, `router` y
   `adapters/`. `domain` no importa FastAPI, SQLAlchemy, Pydantic ni SDKs;
   `service` no importa FastAPI; las rutas no contienen lógica.
   import-linter lo verifica en la CI.
2. Usuario y rol salen siempre de la sesión; un recurso ajeno responde 404.
3. Los DTO del alumno se construyen con lista permitida: nunca soluciones,
   explicaciones ni rúbricas antes de enviar.
4. Toda operación que crea un intento, una corrida, un feedback o una
   sesión de voz exige `Idempotency-Key`.
5. Migraciones solo *expand* (aditivas y compatibles con el código
   anterior). Las tablas legadas no se tocan.
6. Ninguna llamada a un proveedor de pago en pruebas ni en desarrollo: se
   usan los dobles de `adapters/` y `tests/fakes/`.
7. Configuración solo por variables de entorno (`app/core/config.py`); en el
   repo, solo placeholders.
8. Nunca `allow_origins=["*"]` con credenciales; el WebSocket valida
   `Origin` antes de `accept()`.

## Pruebas

- pytest contra PostgreSQL real (no SQLite). Cada prueba corre en una
  transacción que se revierte.
- Las pruebas no tienen red: un guard bloquea todo host que no sea
  localhost.
- E2E con Playwright (Python) contra la app compilada y servida por
  FastAPI, con proveedores falsos.
- Un contrato se prueba: aislamiento con dos cuentas, CSRF, DTO sin claves
  prohibidas, idempotencia concurrente, transacciones.

## Convenciones

- Una rama por change set del plan; Conventional Commits; PR a `main` con
  `ci-gate` en verde; merge commit (nunca squash).
- Código e identificadores en inglés; documentos y textos de interfaz en
  español; material de práctica en inglés.
- El repo es **público**: nada de secretos, datos de clientes o alumnos, ni
  estrategia comercial.
