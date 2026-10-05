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

**Hoy** (`main` @ `133c5e3`) el código es el prototipo de la fase 1: un
backend de lectura con un curso de ejemplo, sin autenticación, sin
frontend, sin pruebas y sin CI. MVP-01 lo reemplaza; su CS-01 reescribe la
sección "Comandos" de este archivo con los comandos reales.

**Comandos objetivo** (existen desde MVP-01 CS-01; no los des por hechos
antes):

```bash
make setup         # uv sync + npm ci
make db-up         # PostgreSQL local (sesión cloud: service postgresql start)
make migrate       # alembic upgrade head
make dev           # backend :8000 + Vite :5173
make test          # pytest (requiere PostgreSQL; sin red ni llaves)
make lint          # ruff + ESLint
make typecheck     # mypy + tsc
make content-lint  # lint de contenido + docs/contenido/cobertura.md
make openapi       # docs/api/openapi.json + tipos del frontend
make e2e           # Playwright (en la CI; local si hay navegadores)
make verify        # todo lo anterior salvo e2e: el check previo a un PR
```

**Prototipo legado** (solo hasta CS-01; requiere Docker, por ejemplo en
GitHub Codespaces):

```bash
cd apps/backend
cp .env.example .env            # solo si no existe
docker compose up -d --build    # Compose v2
docker compose exec backend alembic upgrade head
```

No uses `validate-phase1-final.sh` (espera una migración que ya no es el
head) ni amplíes permisos del socket de Docker.

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
