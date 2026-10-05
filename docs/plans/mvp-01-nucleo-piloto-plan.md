# Plan: mvp-01-nucleo-piloto

- **plan_id:** MVP-01-PLAN-01
- **Spec:** `docs/specs/mvp-01-nucleo-piloto.md` @ `9aa2e2c` (MVP-01-SPEC-01;
  sha256 `17305b26f90cedee38615330901a09d63ddcfb41c13dc2067420972ca419663d`).
  También fijados en `9aa2e2c`: `docs/arquitectura.md` (sha256
  `93850363…eb5b2`) y `docs/contenido/contrato-curricular.md` (sha256
  `84268df9…6aec3`).
- **Ramas:** una por change set, `<tipo>/mvp01-csNN-<nombre>` (p. ej.
  `ci/mvp01-cs01-base`), cada una con su PR a `main`.
- **Lane:** Standard; las acciones de alto riesgo conservan su gate
  (tabla del spec).
- **Estado:** **PENDIENTE DE APROBACIÓN** (gate G0, junto con el spec).
- **Ejecuta:** una sesión cloud de Claude Code con `/goal` (prompt en el
  Proyecto privado). El plan se puede retomar en una sesión nueva sin
  memoria: el estado vive en `STATE.md`.

---

## Contexto de dominio (con procedencia)

- **D1 · Heroku con `heroku.yml`.** Solo generación Cedar y stack
  `container`. `build.docker`, `build.config` (deben corresponder a un `ARG`
  del Dockerfile), `release` con `image` y `command`, y `run.web`. La imagen
  necesita `curl` para transmitir los logs de la release phase. Si la
  release phase falla, la release no se promueve.
  *Fuente: devcenter.heroku.com/articles/build-docker-images-heroku-yml,
  consultado el 5 oct 2026.*
- **D2 · Límites de Heroku.** 30 s al primer byte (H12), ventana rodante de
  55 s en conexiones abiertas, 512 MB de RAM, FS efímero, SIGTERM con 30 s
  para cerrar. *Fuente: spec de migración de CareerAI y HANDOFF §3 @
  `0db81a1`.*
- **D3 · Heroku Postgres Essential-0.** 1 GB, 20 conexiones, sin rollback,
  PG Backups diarios opcionales y gratuitos, mantenimiento y cambios de
  versión sin aviso. *Fuente: devcenter.heroku.com/articles/heroku-postgres-plans,
  5 oct 2026.*
- **D4 · Sesión cloud de Claude Code.** Ubuntu 24.04; Python 3 con uv,
  pytest, ruff y mypy; Node 22 en `PATH`; Docker; PostgreSQL 16 apagado
  (`service postgresql start`); red Trusted (PyPI, npm, GitHub, Docker Hub,
  `mcr.microsoft.com`, Ubuntu); sin Heroku ni Deepgram. Comandos de 2 min
  por defecto y hasta 10. La VM se pausa si la sesión queda inactiva.
  `CLAUDE_CODE_REMOTE=true` en la nube. Hooks `SessionStart` desde
  `.claude/settings.json` del repo. *Fuente: code.claude.com/docs/en/cloud-environments,
  5 oct 2026.*
- **D5 · GitHub desde la sesión.** `git push` a ramas y API REST con `gh
  api`. GraphQL no está disponible: `gh pr create` y `gh pr merge` fallan;
  los PR se abren con `POST /repos/{o}/{r}/pulls` y se mergean con `PUT
  /repos/{o}/{r}/pulls/{n}/merge` (`merge_method=merge`, `sha=<head>`). El
  ruleset se lee con `GET /repos/{o}/{r}/rules/branches/main` (hoy devuelve
  `[]`); la protección clásica y los environments no se pueden leer desde
  la sesión (403). *Fuente: pruebas en la sesión de G0, 5 oct 2026.*
- **D6 · Permisos del agente.** Auto mode permite por defecto pushes a
  cualquier rama del repo, incluida la default, y crear PRs; bloquea force
  push y deploys a producción. Las reglas `permissions.deny` del
  `.claude/settings.json` del repo se aplican antes del clasificador.
  *Fuente: code.claude.com/docs/en/auto-mode-config, 5 oct 2026.*
- **D7 · Patrones de CareerAI** @ `0db81a1` (repo público
  `astraDukoWave/career-ai`, lectura permitida):
  - `.github/workflows/ci.yml`, job `image`: lee `run.web` de `heroku.yml`
    con `sed`, arranca la imagen y sondea `/health` y `/`.
  - `heroku.yml`: flags `--workers 1 --ws-max-size 1048576 --ws-max-queue
    8 --ws-per-message-deflate false`.
  - `backend/tests/test_spa_fallback.py`: pruebas del fallback de la SPA.
  - `e2e/`: Playwright en Python con servidor real y proveedores falsos.
  - Convención: rutas sin lógica; servicios sin FastAPI.
- **D8 · Formato TOEFL iBT 2026.** Contrato curricular §2 *(ets.org, 5 oct
  2026)*.
- **D9 · Reglas de system design aplicadas** (skill `system-design-spec`
  v0.2, destilada de "Backend System Design", Jem Young):
  - Regla 2, patrón de acceso: lecturas de contenido publicado por ruta y
    orden; inserciones de intentos; consultas por alumno y fecha; repasos
    vencidos por `(user_id, due_at)`. Relacional, sin búsqueda de texto.
  - Regla 3: REST para todo en MVP-01 (el WebSocket llega en MVP-02).
  - Reglas 4 y 5: sin caché y sin colas (sin trigger alcanzado).
  - Regla 6: timeouts en toda llamada externa (en MVP-01 solo el TTS del
    workflow).
  - Regla 7: **consistencia** para identidad, intentos, publicación y
    presupuesto (si la base no responde, error explícito, nunca
    "Guardado"); disponibilidad solo para releer contenido ya cargado.
  - Regla 9: sesiones opacas por revocación inmediata (ADR-04).
  - Regla 10: sistemas adyacentes de `docs/arquitectura.md` §15.
- **D10 · Contratos que se preservan.** Historia de Alembic
  (`bc0bb9a48e10` → `816c80672425`); la tabla `users` y sus datos; las
  tablas legadas intactas y **dentro de la metadata de SQLAlchemy** (si no,
  `alembic check` propondría borrarlas): sus modelos pasan a
  `app/modules/legacy/models.py`, congelados, sin servicio ni ruta.

## Cumplimiento de proceso

- Rama creada antes de tocar archivos. Todo entra a `main` por PR, docs
  incluidos. Nunca push directo ni force push a `main`.
- **Check requerido:** `ci-gate`, desde CS-01. Antes de que exista, los
  comandos locales equivalentes, con su output en el PR.
- **Merges** (delegados a este agente solo si Jonathan firma la decisión 1
  de G0). El agente mergea con merge commit, fijando `sha` al head
  revisado, cuando:
  1. `ci-gate` está en verde en ese SHA;
  2. `GET …/rules/branches/main` muestra las reglas `pull_request` y
     `non_fast_forward` (ruleset H-1 activo);
  3. ninguna desviación `pending-human` afecta al change set.
  Si falla (2), no mergea: sigue con el siguiente change set en una rama
  basada en la anterior (PR apilado), lo registra en `STATE.md` y mergea en
  orden cuando el ruleset exista. Sin delegación, deja cada PR listo y
  pasa al siguiente con el mismo apilamiento.
- **Prohibido al agente:** desplegar; crear, leer o pedir secretos; llamar
  APIs de pago; publicar contenido para alumnos; invitar personas; cambiar
  ajustes del repo; borrar ramas ajenas; ampliar alcance fuera del spec.
- **Desviaciones:** detenerse en ese punto, registrarla en `STATE.md` con
  disposición `pending-human`, seguir con el trabajo independiente y parar
  solo si todo lo restante depende de ella. Un "OK" informal no es
  disposición.
- **Verificación independiente:** CS-03, CS-04 y CS-12 pasan por un
  verificador de contexto fresco (subagente con solo spec, diff y
  evidencia) antes del merge; sus hallazgos se reportan aparte en el PR.
- **Estado:** al cerrar cada change set, una línea en el registro de
  `STATE.md`: CS, PR, SHA, URL del run de CI y evidencia. Procedimiento y
  formatos: `docs/sdd/proceso.md`.

## Change sets

### CS-01 · Base reproducible y CI mínima

- **Rama:** `ci/mvp01-cs01-base`.
- **Archivos:**
  - `apps/backend/pyproject.toml`, `uv.lock`, `.python-version` (3.12),
    `.importlinter`.
  - `apps/backend/app/core/{config,logging,errors,clock}.py`,
    `app/db/{engine,session,uow,base}.py`, `app/modules/legacy/models.py`,
    `app/modules/identity/models.py` (el `User` existente, sin cambios de
    esquema), `app/main.py` (`create_app()`), `alembic/env.py`.
  - `apps/backend/tests/` (`conftest.py`, `test_health.py`,
    `test_settings.py`, `test_import_contracts.py`,
    `fixtures/legacy_seed.sql`).
  - `Makefile`, `scripts/dev/cloud-session-start.sh`,
    `.claude/settings.json` (agrega el hook; conserva las reglas `deny`),
    `docker-compose.yml`, `.env.example`, `.github/workflows/ci.yml`,
    `AGENTS.md`, `content/_legacy/clase-10-comparativos.md`.
  - Se eliminan: `validate-phase1-final.sh`, `apps/backend/requirements.txt`,
    `apps/backend/Dockerfile`, `apps/backend/app/api/`,
    `apps/backend/app/schemas/` y `apps/backend/app/db/seed.py` (después de
    exportar su contenido).
- **Qué hacer:**
  - `Settings` con `DATABASE_URL` (obligatoria; normaliza `postgres://` a
    `postgresql+psycopg://`), `APP_ENV` (`dev` | `test` | `prod`),
    `APP_NAME` (por defecto `PCRE`), `APP_ORIGIN`, `DEV_ALLOWED_ORIGINS`,
    `LOG_LEVEL`, `LOG_SALT`, `SESSION_ABSOLUTE_DAYS=7`,
    `SESSION_IDLE_HOURS=24`, `INVITATION_TTL_HOURS=72`,
    `RESET_TTL_HOURS=24`, `REVIEW_INTERVALS_HOURS=24,72,168`,
    `CONSENT_VERSION`, `PRIVACY_CONTACT_EMAIL`, `CONTENT_DIR`, `MEDIA_DIR`,
    `FRONTEND_DIST`, `TEST_CLOCK_ENABLED`. Con `APP_ENV=prod`, la app no
    arranca sin `APP_ORIGIN` ni con `TEST_CLOCK_ENABLED`.
  - Engine con `pool_size=5`, `max_overflow=5`, `pool_pre_ping`; sesiones
    y UoW (context manager con commit al final); `DeclarativeBase` de
    SQLAlchemy 2. Los modelos legados se mueven sin cambios a
    `modules/legacy` para que sigan en la metadata.
  - Logging JSON con `request_id` y sin campos prohibidos
    (`docs/arquitectura.md` §7).
  - `/health` (sin base de datos) y `/api/v1/ready` (`SELECT 1` + revisión
    de Alembic aplicada igual al head del código).
  - Contratos de import-linter de `docs/arquitectura.md` §4 y una prueba que
    crea un módulo temporal que los viola y comprueba que `lint-imports`
    falla.
  - Fixtures de pytest: base `pcre_test` migrada a head una vez por sesión,
    una transacción con savepoint por prueba, `TestClient`, reloj falso y
    guard de red (`pytest-socket` permitiendo solo localhost).
  - Exportar la lección de `seed.py` a
    `content/_legacy/clase-10-comparativos.md` con la regla de comparativos
    corregida y una nota de procedencia (contrato §14).
  - `Makefile`: `setup`, `db-up`, `db-reset`, `migrate`, `dev`, `test`,
    `lint`, `typecheck`, `verify` (por ahora, las partes del backend; los
    demás objetivos se suman en su change set).
  - `cloud-session-start.sh`: sale si `CLAUDE_CODE_REMOTE` no es `true`;
    arranca PostgreSQL (con `sudo -n` si hace falta), espera `pg_isready`,
    crea de forma idempotente el rol `pcre` y las bases `pcre` y
    `pcre_test`, corre `uv sync` y, si existe el lockfile del frontend y
    cambió, `npm ci`; imprime un resumen y siempre sale con 0, con las
    fallas a la vista.
  - Hook `SessionStart` (`matcher: startup|resume`, `timeout: 600`).
  - `docker-compose.yml`: solo el servicio `db` (PostgreSQL 16) para
    Codespaces; la app corre con `make dev`.
  - CI: jobs `backend`, `migrations` y `workflows` (actionlint), más
    `ci-gate` (id y `name` del job iguales, para que el check se llame
    exactamente `ci-gate`) con `needs` de todos, `if: always()` y falla si
    alguno terminó en `failure` o `cancelled`. El job `migrations` sube a
    `816c80672425`, carga `fixtures/legacy_seed.sql`, sube a head, corre
    `alembic check` y prueba downgrade y upgrade de cada migración nueva en
    una base desechable.
- **Verificación:** run de CI en verde en el PR `[ci-run]`; output de `make
  verify` en el cuerpo del PR (esta ventana); prueba de violación del
  import-linter en verde.
- **Commits:** `build(backend): migrate to uv and Python 3.12` ·
  `refactor(backend): module layout, settings and db layer` ·
  `test(backend): pytest harness with PostgreSQL and network guard` ·
  `ci: add CI with backend, migrations and ci-gate` · `chore: cloud session
  bootstrap and remove obsolete scripts`.

### CS-02 · Frontend base, estáticos e imagen de producción

- **Rama:** `feat/mvp01-cs02-frontend-image`.
- **Archivos:** `apps/frontend/` (`package.json`, `package-lock.json`,
  `vite.config.ts`, `tsconfig.json` estricto, `eslint.config.js`,
  `src/app/`, `src/styles/tokens.css`, `src/i18n/es.ts`,
  `src/components/`, `src/api/`, `src/pages/NotFound.tsx`);
  `apps/backend/app/http/static.py`; `scripts/openapi/export.py`;
  `docs/api/openapi.json`; `Dockerfile` (raíz); `.dockerignore`;
  `heroku.yml`; `ci.yml`; `Makefile`.
- **Qué hacer:**
  - Vite + React + TypeScript estricto; React Router (modo librería);
    TanStack Query; `openapi-fetch` con tipos de `openapi-typescript`.
  - Wrapper del cliente: agrega `X-CSRF-Token` en métodos no seguros,
    genera `Idempotency-Key` en las operaciones que lo exigen, expone el
    `request_id` de los errores y redirige a acceso ante un 401.
  - Tokens y tipografías de "Dirección visual" (`@fontsource` de Atkinson
    Hyperlegible Next y Literata; si Next no está empaquetada, Atkinson
    Hyperlegible, registrando la sustitución en el PR). Primitivas:
    `Button`, `Field`, `Notice`, `Page`, `ActionBar`, `MarginNote`,
    `Highlight`. Textos en `src/i18n/es.ts`.
  - Backend: `/assets` desde `FRONTEND_DIST` con caché inmutable, `/media`
    desde `MEDIA_DIR` y fallback de la SPA solo para `GET` con `Accept:
    text/html` fuera de `/api`, `/ws`, `/media`, `/assets` y `/health`.
    Pruebas al estilo de `test_spa_fallback.py` de CareerAI.
  - `make openapi`: exporta el OpenAPI sin levantar servidor y regenera los
    tipos con `npm run gen:api`.
  - `Dockerfile` multietapa: `node:22-slim` compila; `python:3.12-slim`
    con `curl` y `uv` (sin dependencias de desarrollo), usuario no root;
    copia el backend a `/srv/backend`, el `dist` a `/srv/frontend/dist` y
    `content/` a `/srv/content`. Sin `CMD`: el arranque vive en
    `heroku.yml`.
  - `heroku.yml`: `build.docker.web`, `release` (por ahora solo `alembic
    upgrade head`; CS-04 suma la importación) y `run.web` con el comando de
    `docs/arquitectura.md` §11.
  - CI: jobs `frontend` (`npm ci`, typecheck, ESLint, Vitest, build),
    `contract` (OpenAPI y tipos sin diferencias) e `image` (build; red
    Docker con `postgres:16`; migración dentro de la imagen; arranque con
    `run.web` leído de `heroku.yml`; sondas de AC-17; grep del bundle de
    AC-18). Todos en `needs` de `ci-gate`.
- **Verificación:** CI en verde `[ci-run]`; pruebas del fallback; sondas
  del job `image`.
- **Commits:** `feat(frontend): Vite React TypeScript app with design
  tokens` · `feat(backend): serve SPA and media with strict fallback` ·
  `build: production Dockerfile and heroku.yml` · `ci: frontend, contract
  and image jobs`.

### CS-03 · Identidad, sesiones y seguridad base

- **Rama:** `feat/mvp01-cs03-identity`.
- **Archivos:** migración `identity_v1`;
  `app/modules/identity/{domain,service,ports,models,repository,schemas,router}.py`;
  `app/http/{middleware,csrf,deps,errors}.py`; `app/core/security.py`;
  `app/cli.py`; `app/modules/identity/data_registry.py`;
  `apps/frontend/src/features/auth/`, `src/features/profile/`,
  `src/pages/{AcceptInvite,Login,Onboarding,Profile,Privacy}.tsx`,
  `src/features/admin/users/`; pruebas.
- **Qué hacer:**
  - Migración: columnas nuevas de `users` (`docs/arquitectura.md` §5.1;
    emails existentes a minúsculas) y tablas `auth_sessions`,
    `invitations` y `password_reset_tokens`. Desde aquí, toda FK hacia
    `users` lleva `ON DELETE CASCADE`.
  - Dominio puro: política de contraseñas; generación y hash de tokens;
    reglas de vencimiento absoluto e inactividad con `Clock`.
  - Servicios: crear invitación (admin), aceptarla (consumir, crear
    usuario, consentimiento, mayoría de edad, sesión), login con límite de
    intentos y rotación, logout, `GET`/`PATCH /me` con lista explícita de
    campos, enlace de reset, confirmación de reset (revoca todo), revocar
    sesiones, marcar interno, exportar y borrar cuenta.
  - **Registro de datos del alumno** (`data_registry.py`): toda tabla con
    `user_id` se registra con sus reglas de exportación y borrado. Una
    prueba recorre la metadata y falla si una tabla con `user_id` no está
    registrada; así ningún módulo posterior olvida sus datos.
  - HTTP: middleware de `request_id` (`X-Request-ID`), cabeceras de
    seguridad con la CSP de `docs/arquitectura.md` §7, verificación de CSRF
    y `Origin` en métodos no seguros, sobre de errores, límite de cuerpo,
    `current_user` y `require_admin`.
  - CLI: `create-admin-invite --email`, `invite --email`, `reset-link
    --email` (imprimen el enlace una vez).
  - Frontend: aceptar invitación (contraseña, aviso de privacidad con su
    versión y mayoría de edad), login, onboarding de la meta, perfil
    (editar, descargar datos, borrar cuenta), página de privacidad mínima
    (texto completo en CS-10) y admin de usuarios (invitar, copiar enlace,
    reset, revocar, interno).
- **Verificación:** pruebas de AC-05, AC-06 (endpoints de identidad), AC-07,
  AC-19 y AC-22 (parte de identidad); prueba de completitud del registro de
  datos; verificador independiente antes del merge; CI en verde.
- **Commits:** `feat(identity): invitations, sessions and CSRF` ·
  `feat(identity): profile, goals, export and account deletion` ·
  `feat(frontend): access, onboarding and profile screens` · `feat(cli):
  admin invite and reset links`.

### CS-04 · Contenido como código y flujo editorial (backend)

- **Rama:** `feat/mvp01-cs04-content`.
- **Archivos:** migración `content_v1`; `app/modules/content/{schema,loader,lint,coverage,importer,domain,service_editorial,service_delivery,models,repository,schemas,router_admin,router_student}.py`;
  `app/cli.py` (`content lint`, `content import`);
  `content/toefl-ibt-2026-b1-b2/{path,objectives,sources,rubrics}.yaml`;
  `docs/contenido/cobertura.md`; `heroku.yml` (release con importación);
  `ci.yml` (job `content`); `tests/contract/test_student_dto.py`.
- **Qué hacer:**
  - Esquema ejecutable del contrato §9 (Pydantic) y JSON canónico para el
    hash.
  - Lint con todas las reglas de REQ-07 (errores y advertencias) y
    `make content-lint`, que regenera `cobertura.md` de forma determinista.
  - `objectives.yaml` con los objetivos de las 8 unidades (para que la
    cobertura muestre lo pendiente desde el inicio); `sources.yaml` con
    ETS (página de contenido y blueprint 2026), la escala global del MCER y
    las referencias lingüísticas que se usen; `rubrics.yaml` con las cuatro
    rúbricas del contrato §8.
  - Importador: valida todo antes de escribir; una transacción; upsert de
    estructura; revisión `draft` solo si cambió el hash; guarda
    `source_path` y `source_commit`; nunca aprueba ni publica.
  - Dominio de revisiones: máquina de estados, reglas para aprobar
    (hallazgos materiales en cero, lint sin errores, audio revisado) y
    publicación atómica con `superseded`; retiro; bitácora
    `editorial_decisions`.
  - Entrega al alumno: el constructor de DTO con lista permitida. La
    prueba de contrato de AC-08 recorre los endpoints de alumno registrados
    y falla si aparece una clave prohibida; los change sets siguientes
    registran ahí sus endpoints.
  - Endpoints de admin de contenido y `POST /content-reports`.
  - `heroku.yml`: la release suma `python -m app.cli content import --dir
    /srv/content`.
- **Verificación:** AC-11; importar dos veces no crea revisiones nuevas;
  un archivo inválido no escribe nada; pruebas de cada regla del lint;
  job `content` en verde; verificador independiente antes del merge.
- **Commits:** `feat(content): content schema, lint and coverage` ·
  `feat(content): idempotent draft importer` · `feat(content): revisions,
  findings, approval and publication` · `ci: content job`.

### CS-05 · Primera lección de extremo a extremo (U1 · L1)

- **Rama:** `feat/mvp01-cs05-first-lesson`.
- **Archivos:** migración `practice_v1` (`enrollments`, `lesson_progress`,
  `served_aids`, `attempts`, `idempotency_records`, `review_schedule`);
  `app/modules/practice/`; `app/modules/progress/{domain,models}.py`;
  `content/toefl-ibt-2026-b1-b2/units/u1-informacion-decisiones/l1-lectura.yaml`;
  `apps/frontend/src/features/{path,lesson,activities/choice}/`;
  `app/cli.py` (`dev-seed`); `e2e/` (`conftest.py`,
  `test_first_lesson.py`); `ci.yml` (job `e2e`).
- **Qué hacer:**
  - Corrección determinista de `choice` (dominio); `POST /aids` con
    registro en `served_aids` y negación en comprobación; `POST /attempts`
    con idempotencia en la misma transacción que el intento, el progreso y
    el repaso.
  - Regla de repaso 1/3/7 completa en `progress/domain.py` (pura, con
    `Clock`) y su actualización transaccional; los endpoints y la interfaz
    de repasos llegan en CS-08.
  - Inscripción automática, revisión fijada por lección y última
    respuesta por actividad en el DTO.
  - Frontend: ruta, unidad y reproductor de lección (estímulo, pregunta,
    pista, feedback con `MarginNote` y `Highlight`, siguiente);
    `ChoiceRenderer`; estados de carga, error y sin conexión; borrador de la
    respuesta en `sessionStorage` (comodidad local, nunca la fuente de
    verdad).
  - Contenido: L1 de lectura según el contrato §13 (4 ítems de práctica +
    4 de repaso, bloque PCRE, 2 ejemplos y tarea de aplicación).
  - `python -m app.cli dev-seed` (solo con `APP_ENV` `dev` o `test`; se
    niega en `prod`): crea un admin y una alumna de prueba, importa el
    contenido y lo aprueba y publica con el revisor `fixture:dev`, visible
    como fixture en el panel.
  - E2E: Playwright (Python) con un servidor uvicorn real, el frontend
    compilado, la base de prueba y el reloj de prueba. Primer escenario de
    AC-14 (invitación → aceptación → L1 → recarga → respuestas
    persistidas → segunda cuenta aislada).
- **Verificación:** AC-09 (incluida la prueba concurrente), AC-10
  (`choice`), primer tramo de AC-14; job `e2e` en verde `[ci-run]`.
- **Commits:** `feat(practice): attempts, idempotency and served aids` ·
  `feat(progress): spaced review rule` · `feat(frontend): path, unit and
  lesson player` · `feat(content): add U1 reading lesson draft` ·
  `test(e2e): first lesson end to end` · `ci: e2e job`.

### CS-06 · Formatos restantes, audio y escenario en modo texto

- **Rama:** `feat/mvp01-cs06-formats-audio`.
- **Archivos:** dominio y servicio de `practice` (corrección de
  `word_completion`, `sentence_order` y `guided_dialogue`; autoevaluación);
  `apps/frontend/src/features/activities/{word-completion,sentence-order,short-writing,recorded-speaking,guided-dialogue,audio-player}/`;
  `content/…/units/u1-informacion-decisiones/{l2-escucha,l3-escritura,l4-habla,escenario}.yaml`;
  `content/…/audio/manifest.yaml`; `scripts/content/generate_audio.py`;
  `.github/workflows/content-audio.yml`; pruebas y E2E.
- **Qué hacer:**
  - Corrección y validación por formato según REQ-10 y contrato §9.
  - Autoevaluación con rúbrica y ejemplo comentado; reformulación con
    `revision_of`.
  - Grabación local con MediaRecorder, sin subir nada, y camino de
    micrófono denegado.
  - `guided_dialogue` sobre el grafo del escenario.
  - Reproductor de audio con reintento y conteo de reproducciones;
    transcripción solo como ayuda servida.
  - `generate_audio.py` detrás de un puerto `TextToSpeech` (adaptador
    Deepgram Aura-2 y doble). `--dry-run` cuenta caracteres y estima el
    costo sin red. El manifiesto exige proveedor real: el lint rechaza
    audio de un proveedor falso dentro de `content/`.
  - `content-audio.yml`: `workflow_dispatch` (inputs `unit` y
    `max_chars`), environment `content-audio`, secret `DEEPGRAM_API_KEY`,
    permisos `contents: write` y `pull-requests: write` solo en ese
    workflow; aborta si el conteo supera `max_chars`; publica el costo
    estimado en el resumen del run y abre un PR con los MP3 y el
    manifiesto.
  - Contenido U1: escucha, escritura, habla y escenario (grafo de texto +
    campos para el coach de MVP-02).
- **Verificación:** AC-10 completo; E2E de cada formato con teclado;
  actionlint de `content-audio.yml`; output de `generate_audio.py
  --dry-run` en el PR.
- **Commits:** `feat(practice): grading for completion, ordering and
  dialogue` · `feat(frontend): remaining activity renderers` ·
  `feat(content): U1 listening, writing, speaking and scenario drafts` ·
  `build(content): TTS generation script and workflow`.

### CS-07 · Comprobaciones: diagnóstico inicial y checkpoint U1

- **Rama:** `feat/mvp01-cs07-assessments`.
- **Archivos:** migración `assessment_v1`; servicio y rutas de corridas en
  `practice`; `apps/frontend/src/features/assessment/`;
  `content/…/assessments/inicial.yaml`; `content/…/units/u1-…/checkpoint.yaml`;
  pruebas y E2E.
- **Qué hacer:** REQ-12 completo: inicio con orden fijado, respuestas
  guardadas sin feedback, envío idempotente, resultados por objetivo, una
  corrida de diagnóstico (reinicio por admin), checkpoint repetible y
  numerado, ítem "no evaluable (audio)" y la etiqueta formativa.
  Diagnóstico con 12 cerrados, 2 escritas y 2 orales que reparten objetivos
  de U1–U8 (contrato §5).
- **Verificación:** AC-08 en modo comprobación; pruebas de orden fijo,
  retomar corrida, diagnóstico único y checkpoint numerado; E2E del
  diagnóstico (subconjunto).
- **Commits:** `feat(practice): assessment runs` · `feat(frontend):
  assessment and results screens` · `feat(content): initial diagnostic
  and U1 checkpoint drafts`.

### CS-08 · Progreso, repasos e inicio

- **Rama:** `feat/mvp01-cs08-progress`.
- **Archivos:** `app/modules/progress/{service,repository,schemas,router}.py`;
  `app/http/test_clock.py` (solo `APP_ENV=test`);
  `apps/frontend/src/features/{home,progress,reviews}/`; pruebas y E2E.
- **Qué hacer:** métricas de REQ-13 con denominadores y "aún sin
  medición"; racha por día local; selección de repasos (pool `review`,
  `repeated`); "Continuar"; endpoints `/me/progress`, `/me/reviews` y
  `/me/reviews/next`; `POST /api/test/clock` con la guardia de arranque en
  `prod`.
- **Verificación:** AC-12 y AC-13 (fixture con números exactos); E2E con
  reloj +24 h y repasos vencidos (tramo de AC-14); prueba de que `prod` no
  arranca con el reloj de prueba.
- **Commits:** `feat(progress): metrics, streak and reviews` ·
  `feat(frontend): home, progress and reviews` · `test(e2e): next-day
  reviews with test clock`.

### CS-09 · Panel editorial, reportes y feedback del piloto

- **Rama:** `feat/mvp01-cs09-editorial-pilot`.
- **Archivos:** migración `insights_v1`; `app/modules/insights/`;
  emisión de eventos en los servicios;
  `apps/frontend/src/features/admin/{content,reports,pilot}/`,
  `src/features/feedback/`; pruebas y E2E.
- **Qué hacer:**
  - `user_feedback`, `product_events` (lista cerrada de REQ-16) y
    `error_events` (middleware que registra los 5xx; limpieza de más de 30
    días al arrancar).
  - Panel editorial: lista, detalle, vista previa como alumno (práctica y
    comprobación), claves, fuentes, hallazgos, aprobar, publicar, publicar
    unidad y retirar.
  - Reportes de contenido con triage y panel del piloto de REQ-15.
  - Alumno: valoración por lección, "Enviar comentario" y "Reportar un
    problema".
- **Verificación:** E2E en el que un admin publica una revisión nueva y el
  historial anterior queda intacto (tramo de AC-14); AC-23 con fixture;
  pruebas de guardas de rol.
- **Commits:** `feat(insights): feedback, events and error events` ·
  `feat(frontend): editorial panel` · `feat(frontend): pilot dashboard and
  learner feedback`.

### CS-10 · Seguridad final, textos legales, accesibilidad, rendimiento y deploy

- **Rama:** `feat/mvp01-cs10-hardening-deploy`.
- **Archivos:** pruebas de cabeceras, CSP, límites y Markdown;
  `apps/frontend/src/legal/{privacidad,terminos,como-funciona}.md` y sus
  páginas; `e2e/test_accessibility.py` (axe, teclado, viewport de
  teléfono); `scripts/perf/smoke.py`; `.github/workflows/deploy.yml`;
  `docs/runbook.md`.
- **Qué hacer:**
  - Revisión final de seguridad contra `docs/arquitectura.md` §7.
  - Textos legales en borrador (REQ-17) con encabezado de versión igual a
    `CONSENT_VERSION` y la nota "Borrador pendiente de revisión" en el
    repo.
  - Accesibilidad: axe en las seis pantallas de AC-15, recorrido completo
    con teclado y proyecto de Playwright con viewport de teléfono.
  - `smoke.py`: 10 peticiones concurrentes contra el build de producción
    local, p95 por endpoint; se corre y se guarda el resultado.
  - `deploy.yml` según REQ-03: `workflow_run` del CI en `main`, condición
    `vars.DEPLOY_ENABLED == 'true'`, environment `production`,
    concurrencia `production`, verificación de secret y variable con el
    mensaje "deploy no configurado", instalación de la CLI de Heroku,
    `heroku pg:backups:capture`, `git push` al remoto de Heroku, espera de
    la release y smoke; si algo falla, imprime el comando de rollback.
  - `docs/runbook.md`, con comandos exactos y lo que se debe ver en cada
    paso: preparación de Heroku (app Cedar, stack `container`, Postgres
    Essential-0, programación de backups, config vars), preparación de
    GitHub (environment con revisor **antes** del secret, variables),
    aprobación y verificación de un deploy, rollback, logs, ensayo de
    restauración en una base desechable, admin inicial con `heroku run`,
    invitaciones, publicación de una unidad, run de audio y primeros pasos
    ante un incidente.
- **Verificación:** AC-15, AC-19, AC-20 (resultado registrado), AC-21 (el
  run omitido de `deploy.yml` tras el merge, con su URL); actionlint.
- **Commits:** `feat(security): headers, limits and markdown safety` ·
  `feat(frontend): legal and how-it-works pages (draft)` · `test(e2e):
  accessibility, keyboard and mobile` · `perf: smoke script and baseline` ·
  `ci: approved deploy workflow to Heroku` · `docs: runbook`.

### CS-11 · Contenido U1 listo para revisión

- **Rama:** `feat/mvp01-cs11-u1-ready`.
- **Archivos:** `content/toefl-ibt-2026-b1-b2/` (U1 y diagnóstico),
  `scripts/content/review_packet.py`, `Makefile` (`review-packet`),
  `docs/contenido/revision/u1.md`, `docs/contenido/cobertura.md`.
- **Qué hacer:**
  - Segunda pasada de todo el contenido de U1 y del diagnóstico con la
    lista de revisión del contrato §12: claves, variantes, distractores,
    fuentes por regla, apoyo en español, extensiones y accesibilidad.
  - Marcar cada ítem `ready-for-review` en su archivo.
  - `make review-packet UNIT=u1` genera el paquete de revisión de REQ-08 de
    MVP-03; la CI comprueba que esté al día.
- **Verificación:** AC-16; lint y cobertura sin errores `[ci-run]`.
- **Commits:** `feat(content): U1 ready for review` · `build(content):
  review packet generator`.

### CS-12 · Cierre de MVP-01

- **Rama:** `docs/mvp01-cs12-close`.
- **Qué hacer:**
  - `verify` contra el spec: un verificador de contexto fresco revisa
    spec, diffs y evidencia; esta ventana corre `make verify` en una sesión
    limpia y consolida `docs/reviews/mvp-01-verify.md` con el formato de la
    skill `verify` (evidencia por AC, con etiqueta).
  - `cto-review` de activación: `docs/reviews/mvp-01-activacion-cto-review.md`
    con los gates G1 (deploy), G2 (audio), G3 (publicación) y G4 (alumnos
    reales), cada uno con rollback, blast radius, dueño, observabilidad y su
    mensaje de aprobación listo para pegar.
  - `HANDOFF.md`, `STATE.md`, `README.md` (portafolio: qué es, cómo
    correrlo, arquitectura y enlaces a las decisiones) y `AGENTS.md`.
- **Verificación:** AC-01, AC-02 y AC-24; el reporte no tiene ❌ abiertos.
- **Commit:** `docs: close MVP-01 with verify report and activation review`.

## Tareas [HUMANO]

- **H-1 · Ruleset de `main`** (antes del primer merge). En
  `https://github.com/astraDukoWave/pcre-learning-platform/settings/rules`
  → **New ruleset** → **New branch ruleset**. Nombre `main`;
  *Enforcement status* **Active**; *Target branches* → **Add target** →
  **Include default branch**. Reglas: **Restrict deletions**, **Require a
  pull request before merging** (aprobaciones requeridas: 0) y **Block
  force pushes**. **Create**.
  Evidencia: "ruleset activo". El agente lo comprueba con `gh api
  repos/astraDukoWave/pcre-learning-platform/rules/branches/main`.
- **H-1b · `ci-gate` como check requerido** (después del primer run de CI
  de CS-01). Editar el ruleset `main` → **Require status checks to pass** →
  **Add checks** → escribir `ci-gate` y elegirlo → **Save changes**.
  Evidencia: "ci-gate requerido". La respuesta de `rules/branches/main`
  incluye `required_status_checks`.
- **H-6 · Prueba manual en teléfonos** (después de G1): en un iPhone
  (Safari) y un Android (Chrome), con la URL de Heroku, recorrer
  aceptación, una lección de cada habilidad (grabar y reproducir), el
  checkpoint y el panel. Evidencia: checklist marcado del runbook y
  capturas de lo que falle.
- **G1–G4** (activación): los pasos exactos quedan en
  `docs/reviews/mvp-01-activacion-cto-review.md` y en el runbook al cerrar
  CS-12. Resumen: G1 crear Heroku y GitHub environment y aprobar el primer
  deploy; G2 aprobar el run de audio de U1 y revisar los MP3; G3 revisar y
  publicar U1 en el panel; G4 aprobar los textos legales, ensayar la
  restauración, crear tu admin con `heroku run` e invitar.

## Orden y dependencias

```
H-1 ─┐
CS-01 ─ H-1b ─ CS-02 ─ CS-03 ─ CS-04 ─ CS-05 ─ CS-06 ─ CS-07 ─ CS-08 ─ CS-09 ─ CS-10 ─ CS-11 ─ CS-12
                                                                                              └─ G1 ─ G2 ─ G3 ─ H-6 ─ G4
```

- Sin H-1, los PR se apilan (ver Cumplimiento de proceso).
- CS-06, CS-07 y CS-08 dependen de CS-05 y siguen ese orden porque
  comparten migraciones.
- G1–G4 son de Jonathan y no bloquean el cierre de MVP-01 ni el arranque
  de MVP-02.

## Tests requeridos

| Qué | Dónde |
|---|---|
| Dominio: contraseñas, tokens y vencimientos, corrección por formato, repaso 1/3/7, máquina de estados editorial, métricas | pytest (esta ventana y CI) |
| Integración con PostgreSQL: idempotencia concurrente, transacción intento + repaso, importador atómico, registro de datos del alumno, migraciones | pytest y job `migrations` |
| Contrato: DTO sin claves prohibidas, OpenAPI y tipos sin diferencias, contratos de import | pytest, jobs `contract` y `backend` |
| Seguridad: aislamiento con dos cuentas, CSRF, `Origin`, cabeceras, cookie, límites, Markdown | pytest |
| E2E: flujo de AC-14, formatos con teclado, comprobación, repasos con reloj, publicación editorial, accesibilidad y teléfono | job `e2e` |
| Imagen: build y arranque con `heroku.yml`, sondas, grep del bundle | job `image` |
| Contenido: lint, mínimos y cobertura | job `content` |
| Rendimiento | `scripts/perf/smoke.py`, resultado registrado |
| Teléfonos reales | [HUMANO] H-6 |

## Riesgos → mitigación

- **El agente se desvía o infla el alcance** → spec con DoD binario,
  `ci-gate`, import-linter, verificadores independientes en CS-03, CS-04 y
  CS-12, y `STATE.md` por change set.
- **Contenido de baja calidad** → lint, mínimos, segunda pasada en CS-11,
  paquete de revisión y publicación solo humana.
- **La sesión se queda sin presupuesto de uso o se pausa** → push en cada
  checkpoint verde; `STATE.md` y el plan permiten retomar en una sesión
  nueva.
- **Ruleset no configurado** → apilamiento de PRs sin merge.
- **E2E inestable** → esperas explícitas, reloj de prueba y artefactos de
  traza en las fallas; nada de `sleep` fijo.
- **Imagen distinta a la de producción** → la CI arranca exactamente
  `run.web` de `heroku.yml`.
- **Fuga de datos en un repo público** → solo placeholders; grep del bundle;
  nada de datos de clientes en contenido ni fixtures.

## Prompt de respaldo

No va en el repo (regla de la skill `design-plan`). El prompt de arranque
con `/goal` vive en el Proyecto privado "English StartUp"; cualquier sesión
puede retomar este plan leyendo `CLAUDE.md`, `HANDOFF.md` y `STATE.md`.

---

*Generado: 5 oct 2026 · Basado en MVP-01-SPEC-01 @ `9aa2e2c` · Estado:
pendiente de aprobación (G0).*
