# PCRE Learning Platform

Plataforma de práctica de inglés B1 → B2 para hispanohablantes que lo necesitan para trabajo
o estudios. La primera ruta, `toefl-ibt-2026-b1-b2`, usa tareas del estilo TOEFL iBT (formato
2026) como preparación independiente y formativa: no es material oficial de ETS ni promete
puntajes.

"PCRE" (Pattern, Concept, Rules, Examples) es el formato de explicación de cada lección y el
nombre de trabajo del proyecto.

## Qué hace (MVP-01)

- Acceso solo por invitación, con aviso de privacidad versionado, exportación y borrado de
  cuenta.
- Ruta con diagnóstico inicial, lecciones de lectura, escucha, escritura y habla, un escenario
  de transferencia y un checkpoint por unidad; la Unidad 1 está escrita y lista para revisión.
- Corrección determinista con variantes válidas, ayudas registradas, autoevaluación con
  rúbrica, repaso espaciado (1, 3 y 7 días) y progreso con métricas definidas.
- Contenido como código (YAML con lint, cobertura y paquete de revisión) y flujo editorial en
  la base: aprobar por hash, publicar y retirar sin perder historial.
- Panel del piloto: actividad, valoraciones, reportes de contenido y errores.

MVP-02 (coach con IA y voz) llega apagado y con topes de gasto; MVP-03 completa las unidades
2 a 8. El estado real vive en [`STATE.md`](STATE.md) y [`HANDOFF.md`](HANDOFF.md).

## Arquitectura

Monolito modular: FastAPI + PostgreSQL en `apps/backend/` sirve la API, el audio y la SPA de
React + Vite + TypeScript (`apps/frontend/`) desde el mismo origen. Se despliega en Heroku
(stack `container`) con `Dockerfile` y `heroku.yml`; el deploy solo corre desde GitHub
Actions con aprobación humana.

```
Navegador (SPA) ── mismo origen ──► web dyno (uvicorn, 1 worker)
                                     ├─ /api/v1 · /media · /assets
                                     ├─ release: alembic upgrade head + importación de contenido
                                     └─ PostgreSQL
```

- Módulos `identity`, `content`, `practice`, `progress` e `insights` con capas `domain`,
  `service`, `ports`, `repository` y `router`; import-linter hace cumplir los límites.
- Sesiones opacas en PostgreSQL con cookie `__Host-`, CSRF por token y `Origin`, CSP estricta.
- OpenAPI versionado (`docs/api/openapi.json`) y tipos generados para el frontend.

Decisiones y su porqué: [`docs/arquitectura.md`](docs/arquitectura.md) (ADR-01 a ADR-15).
Specs y planes: [`docs/specs/`](docs/specs) y [`docs/plans/`](docs/plans). Reglas del contenido:
[`docs/contenido/contrato-curricular.md`](docs/contenido/contrato-curricular.md). Operación:
[`docs/runbook.md`](docs/runbook.md).

## Correrlo en local

Requisitos: Python 3.12 con [uv](https://docs.astral.sh/uv/), Node 22 y PostgreSQL 16 (o
Docker para levantarlo).

```bash
git clone https://github.com/astraDukoWave/pcre-learning-platform.git
cd pcre-learning-platform
make setup          # uv sync + npm ci
make db-up          # PostgreSQL local con las bases pcre, pcre_test y pcre_migcheck
make migrate        # alembic upgrade head
cd apps/backend && APP_ENV=dev uv run python -m app.cli dev-seed && cd ../..
make dev            # backend :8000 y Vite :5173
```

`dev-seed` crea `admin@example.com` y `alumna@example.com` (contraseña `practica-local-1`) y
publica el contenido sin bloqueos con el revisor de prueba `fixture:dev`; solo funciona fuera
de producción. Abre http://localhost:5173.

Antes de un PR: `make verify` (lint, tipos, pruebas contra PostgreSQL, migraciones, contenido,
frontend y contrato de la API). El E2E con Playwright corre en la CI (`make e2e` en local).

## Estructura

```
apps/backend/     FastAPI, módulos, migraciones Alembic y pruebas (pytest)
apps/frontend/    React + Vite + TypeScript
content/          rutas de contenido en YAML y manifiesto de audio
docs/             specs, planes, arquitectura, contenido, revisiones y runbook
e2e/              pruebas de punta a punta (Playwright, Python)
scripts/          CI, contenido (audio, paquete de revisión), rendimiento y desarrollo
```

## Cómo se trabaja

Desarrollo guiado por specs: cada ciclo tiene spec y plan aprobados; cada change set entra por
PR con CI verde (`ci-gate`) y merge commit. Los deploys, el audio con TTS, la publicación de
contenido y las invitaciones son acciones humanas con su gate. Guía para agentes de código:
[`AGENTS.md`](AGENTS.md).

## Autor

Jonathan Muñoz ([astradukowave](https://github.com/astraDukoWave)).

## Licencia

Sin licencia abierta por ahora: el código es visible como portafolio. La licencia del contenido
de práctica es una decisión abierta (spec de MVP-01).
