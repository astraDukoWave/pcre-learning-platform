# Arquitectura — PCRE Learning Platform

Versión 1.0 · 5 oct 2026 · Estado: **PENDIENTE DE APROBACIÓN** (gate G0,
junto con `MVP-01-SPEC-01`, `MVP-02-SPEC-01` y `MVP-03-SPEC-01`).
Skill aplicada: `system-design-spec` v0.2 (reglas 0–10).

Fuente de verdad técnica que comparten los tres specs. Un cambio aquí entra
por un spec o por una enmienda versionada al final de este archivo. El
discovery de origen (contrato `PCRE-MVP-20261005` y spec de producto v0.3)
es privado y vive en el Proyecto "English StartUp" de Claude; aquí no se
copia contexto comercial ni datos de clientes.

---

## 1. Qué construimos

Plataforma SaaS de práctica de inglés para hispanohablantes que se
consideran B1 y quieren llegar a B2 para trabajo o estudios. La primera
ruta usa como referencia las tareas del TOEFL iBT vigente desde enero de
2026 (`docs/contenido/contrato-curricular.md`).

Forma: **monolito modular**. Un servicio FastAPI sirve la API
(`/api/v1`), el WebSocket de voz (`/ws`, desde MVP-02), el audio del
contenido (`/media`) y el frontend React compilado. Base de datos:
PostgreSQL gestionado en Heroku.

Restricciones que mandan sobre todo lo demás:

- **Repo público** (portafolio): sin secretos, sin datos de alumnos, sin
  estrategia comercial. Solo placeholders.
- **Un dyno, un proceso** (`--workers 1`) durante el piloto.
- **El agente de desarrollo** trabaja en sesiones cloud de Claude Code, sin
  acceso a Heroku ni llaves de proveedores de pago (§13). Todo lo que
  necesita producción o dinero es una tarea [HUMANO] con gate.
- **Afirmaciones honestas:** preparación independiente y formativa. Sin
  certificados, sin nivel acreditado y sin predicción de puntuaciones ETS.

## 2. Calibración de escala (regla 0)

| Campo | Valor | Naturaleza |
|---|---|---|
| Dimensión | Alumnos activos por semana (WAU) y sesiones de voz simultáneas | — |
| Valor actual | 0: no hay sistema desplegado ni flujo de alumno | `[verified-this-session]` repo @ `133c5e3` |
| Pico esperado | 20 cuentas, 10 peticiones HTTP concurrentes, 3 sesiones de voz | `[supuesto]` de ingeniería (PCRE-MVP-20261005 §3) |
| Horizonte | Primeras 4 semanas de piloto | `[supuesto]` |
| Cohorte prevista | 2–3 personas invitadas + uso interno del responsable | `[supuesto]`, detalle en `strategy.md` (privado) |

**Triggers.** Lo que no se construye hoy entra solo cuando se cumple su
condición medible:

| Cuando… | entonces… | mientras tanto |
|---|---|---|
| p95 > 800 ms en operaciones normales con 10 peticiones concurrentes | Revisar queries e índices; después, cache-aside por `content_hash` | Sin caché |
| WAU > 50, o memoria del dyno > 80 % (R14) | Segundo dyno; mover el rate limiting a PostgreSQL | 1 dyno, 1 worker |
| p95 del feedback de IA > 20 s, o > 5 ejecuciones pendientes de recuperar a la vez | Cola persistente (tabla de jobs) + worker dyno | Petición bajo demanda con timeout |
| > 3 sesiones de voz rechazadas por cupo en una semana | Revisar el cupo global y el tamaño del dyno | Cupo de 3 |
| Audio del contenido > 200 MB | Object storage + CDN | Audio versionado en el repo, servido por la app |
| > 10 alumnos externos, o registro abierto | Email transaccional; sacar contenido y claves del repo público | Invitación y reset manuales |
| Base de datos > 800 MB | Plan Essential-1 | Essential-0 |

Sin uno de estos triggers no entran microservicios, colas, Redis, réplicas
ni sharding.

## 3. Módulos

Backend en `apps/backend/app/`, organizado por módulo (vertical), cada uno
con capas internas.

| Módulo | Responsabilidad | Tablas que posee | Ciclo |
|---|---|---|---|
| `identity` | Usuarios, invitaciones, sesiones, perfil y objetivo, consentimiento, reset asistido, exportación y borrado | `users`, `auth_sessions`, `invitations`, `password_reset_tokens` | MVP-01 |
| `content` | Contenido como código (esquema, lint, cobertura, importación), revisiones, fuentes, hallazgos, aprobación/publicación/retiro, reportes; y la entrega al alumno sin soluciones | `learning_paths`, `units`, `content_items`, `content_revisions`, `activities`, `sources`, `revision_sources`, `review_findings`, `editorial_decisions`, `content_reports` | MVP-01 |
| `practice` | Inscripción, progreso por lección con revisión fijada, ayudas servidas, intentos, corrección determinista, idempotencia, comprobaciones | `enrollments`, `lesson_progress`, `served_aids`, `attempts`, `idempotency_records`, `assessment_runs` | MVP-01 |
| `progress` | Métricas, racha, repaso espaciado, siguiente actividad | `review_schedule` (las métricas se calculan desde `attempts`) | MVP-01 |
| `insights` | Feedback del producto, eventos, errores del servidor, panel del piloto | `user_feedback`, `product_events`, `error_events` | MVP-01 |
| `usage` | Presupuestos, reservas, precios, ejecuciones de IA y voz | `budget_periods`, `ai_runs` | MVP-02 |
| `coaching` | Feedback abierto con IA, transcripción y coach de voz | `voice_sessions` | MVP-02 |

Fuera de los módulos:

- `app/core/`: `Settings`, errores tipados con código, logging JSON, reloj
  (`Clock`), ids y primitivas de seguridad (tokens, hashing).
- `app/db/`: engine, sesión, unidad de trabajo (UoW), metadata y helpers.
- `app/http/`: middleware (request_id, cabeceras de seguridad, CSRF/Origin,
  límite de cuerpo), manejo de errores, dependencias (`current_user`,
  `require_admin`), archivos estáticos y fallback de la SPA.
- `app/bootstrap.py`: único punto de composición; construye adaptadores y
  servicios desde `Settings`.
- `app/main.py`: entrada ASGI (`create_app()`).
- `app/cli.py`: comandos de gestión (invitación de admin, contenido,
  invitaciones, reset).

Capas dentro de cada módulo: `domain` (reglas puras con dataclasses),
`service` (casos de uso; coordina UoW y puertos), `ports` (Protocols de
proveedores y reloj), `models` (ORM), `repository` (consultas), `schemas`
(Pydantic de HTTP), `router` (FastAPI) y `adapters/` (proveedores reales y
dobles de prueba). No hace falta un puerto por tabla: un CRUD
administrativo sin reglas puede ir de `service` a `repository` directo.

## 4. Reglas de dependencia (verificadas en CI)

Contratos de import-linter en `apps/backend/.importlinter`, job requerido:

1. `app.modules.*.domain` no importa `fastapi`, `starlette`, `sqlalchemy`,
   `pydantic`, `httpx`, `websockets`, `google`, ni `app.db`, `app.http`, ni
   `models`, `repository`, `router` o `adapters` de ningún módulo.
2. `app.modules.*.service` no importa `fastapi`, `starlette` ni ningún
   `router`.
3. Un `router` no importa `models` ni `repository`: pasa por servicios.
4. Un módulo usa a otro solo por su `service` o su `domain`. Excepción
   explícita: un `repository` puede **leer** tablas de otro módulo (joins de
   lectura); nunca escribirlas.

Convenciones sin linter: las rutas no contienen lógica (heredado de
CareerAI) y los adaptadores reales solo se construyen en `bootstrap.py`.

Un test rompe a propósito un contrato en un fixture temporal y comprueba
que el linter falla: el contrato se prueba, no se supone.

## 5. Persistencia

- **PostgreSQL 16** en dev y CI (la versión que trae la sesión cloud y el
  servicio de CI). En el piloto, Heroku Postgres **Essential-0**: 1 GB,
  20 conexiones, sin rollback, backups lógicos diarios opcionales y
  gratuitos, mantenimiento y actualizaciones de versión sin aviso
  `[verified-this-session: devcenter.heroku.com/articles/heroku-postgres-plans,
  5 oct 2026]`. No usar extensiones ni sintaxis exclusivas de una versión.
- **SQLAlchemy 2.x síncrono con psycopg 3.** Endpoints `def` en el
  threadpool de FastAPI. En el WebSocket (MVP-02) la base de datos solo se
  toca al reservar y al cerrar, fuera del event loop. Pool de 5 + 5 de
  overflow, para dejar margen a la release phase y a los one-off dynos
  dentro del límite de 20.
- **`DATABASE_URL`** llega de Heroku como `postgres://…` y se normaliza a
  `postgresql+psycopg://…`.
- **Alembic** conserva la historia (`bc0bb9a48e10` → `816c80672425`) y solo
  agrega migraciones *expand*: aditivas y compatibles con la versión
  anterior del código, para que un rollback de código sea seguro. Una
  migración destructiva necesita su propio spec, backup y ensayo de
  restauración. `alembic check` corre en CI.
- **Identificadores:** UUID en toda entidad expuesta por la API. **Dinero:**
  entero en micro-USD (BIGINT). **Tiempo:** `timestamptz` en UTC; el día
  local del alumno se fija al enviar (`local_day`).
- **JSONB** solo para cuerpos tipados (consignas, opciones, respuestas,
  resultados), validados con Pydantic en el borde. Las relaciones viven en
  columnas.
- **Transacciones cortas:** nunca abiertas mientras responde un proveedor.
- **Un GET nunca modifica objetos del ORM** (corrige el hallazgo de
  `courses.py`, §12).

### 5.1 Modelo de datos

**identity**

- `users` (existente, se amplía): `id` UUID · `email` en minúsculas y único
  · `password_hash` (Argon2id) · `role` (`student` | `admin`; nunca lo
  elige el alumno) · `display_name` · `timezone` (IANA, por defecto
  `America/Mexico_City`) · `goal_purpose` (`work` | `studies` |
  `certification` | `other` | `unknown`) · `target_exam`, `target_score`,
  `target_date` (opcionales; "no lo sé" es válido) · `self_reported_level`
  (opcional; nunca se muestra como acreditado) · `is_internal` (excluye de
  las métricas del piloto) · `consent_version`, `consent_accepted_at` ·
  `adult_attested_at` · `last_login_at` · timestamps. MVP-02 agrega
  `voice_notice_accepted_at`.
- `auth_sessions`: `id` · `user_id` · `token_hash` (único) · `csrf_hash` ·
  `created_at` · `last_seen_at` · `absolute_expires_at` ·
  `idle_expires_at` · `revoked_at` · `revoke_reason`.
- `invitations`: `id` · `email` · `role` · `token_hash` (único) ·
  `created_by` · `expires_at` · `consumed_at` · `consumed_user_id`. Un uso.
- `password_reset_tokens`: `id` · `user_id` · `token_hash` (único) ·
  `created_by` · `expires_at` · `consumed_at`. Un uso; consumirlo revoca
  todas las sesiones del usuario.

**content**

- `learning_paths`: `id` · `code` (único, `toefl-ibt-2026-b1-b2`) ·
  `exam_code` · `exam_format_version` · `level_from` · `level_to` · `title`
  · `status` (`draft` | `active` | `archived`) · `catalog_version`. Se
  muestra activa solo si tiene contenido publicado.
- `units`: `id` · `path_id` · `slug` · `position` · `title` · `summary`.
  Únicos `(path_id, slug)` y `(path_id, position)`.
- `content_items`: `id` · `kind` (`lesson` | `assessment_form` |
  `scenario`) · `path_id` · `unit_id` (nulo en formularios de ruta) ·
  `slug` · `position` · `skill` (lecciones) · `form_kind` (`initial` |
  `checkpoint` | `final`) · `published_revision_id`. Único `(path_id, slug)`.
- `content_revisions`: `id` · `item_id` · `version` (monótona) ·
  `content_hash` (sha256 del JSON canónico) · `body` (JSONB validado) ·
  `source_path` · `source_commit` · `status` (`draft` | `approved` |
  `published` | `superseded` | `withdrawn`) · `approved_by`, `approved_at`,
  `approved_hash` · `published_at` · `withdrawn_at`, `withdraw_reason`.
  Únicos `(item_id, version)` y `(item_id, content_hash)`. Una revisión
  aprobada o publicada es inmutable.
- `activities`: `id` · `revision_id` · `activity_key` (estable, viene del
  archivo) · `position` · `format` · `task_family` · `pool` (`practice` |
  `review` | `assessment`) · `objective_codes` · `prompt` · `stimulus` ·
  `options` · `hints` · `support_es` · y los **privados** `solution`,
  `explanation`, `rubric`. Único `(revision_id, activity_key)`.
- `sources` (`url`, `title`, `publisher`, `accessed_on`) y
  `revision_sources` (`revision_id`, `source_id`, `claim`, `scope`,
  `location`): qué respalda cada fuente y con qué alcance. Una cita no
  equivale a respaldo confirmado.
- `review_findings`: `revision_id` · `author` (`user:<id>` o
  `ai:<modelo>`) · `category` · `severity` (`material` | `minor`) ·
  `description` · `status` (`open` | `resolved` | `wont_fix`) ·
  `resolution_note`.
- `editorial_decisions`: bitácora append-only (`approve`, `publish`,
  `withdraw`, `request_changes`) con `decided_by`, `content_hash` y nota.
- `content_reports`: `user_id` · `revision_id` · `activity_id` ·
  `attempt_id` · `category` · `message` (≤ 1 000) · `status`.

**practice**

- `enrollments`: `user_id` · `path_id` · `catalog_version_at_enroll` ·
  `enrolled_at`. Inscripción automática a la única ruta activa.
- `lesson_progress`: `user_id` · `item_id` · `pinned_revision_id` ·
  `started_at` · `completed_at`. La revisión fijada se usa hasta completar
  la lección; si se retira, se libera.
- `served_aids`: `user_id` · `activity_id` · `kind` (`hint` |
  `support_es` | `transcript` | `example`) · `index` · `served_at` ·
  `attempt_id` (se llena al enviar el intento siguiente). Las ayudas las
  sirve el servidor, nunca viajan en el DTO de la lección; en modo
  comprobación se niegan.
- `attempts`: `id` · `user_id` · `activity_id` · `revision_id` · `mode`
  (`practice` | `review` | `assessment`) · `assessment_run_id` ·
  `response` · `aids` (pistas, repeticiones de audio, transcripción,
  apoyo en español, ejemplo) · `evaluation_status` (`evaluated` |
  `pending` | `not_evaluable` | `failed`) · `evaluation_source` (`auto` |
  `self` | `ai` | `human`) · `score` (0–1 o nulo) · `result` ·
  `submitted_at` · `local_day`. Append-only salvo borrado de cuenta.
  Índices `(user_id, submitted_at)` y `(user_id, activity_id)`.
- `idempotency_records`: `user_id` · `operation` · `key` · `request_hash` ·
  `status_code` · `response`. Único `(user_id, operation, key)`; se escribe
  en la misma transacción que el efecto.
- `assessment_runs`: `id` · `user_id` · `form_revision_id` · `status`
  (`in_progress` | `submitted`) · `item_order` (fijado al iniciar) ·
  `started_at` · `submitted_at` · `summary`. Índice único parcial: una
  corrida en curso por usuario y formulario.

**progress**

- `review_schedule`: `user_id` · `objective_code` · `stage` (0–3) ·
  `due_at` · `last_outcome` · `updated_at`. Único `(user_id,
  objective_code)`; índice `(user_id, due_at)`. Se actualiza en la
  transacción del intento.

**insights**

- `user_feedback`: `user_id` · `context_type` (`lesson` | `general` |
  `voice` | `ai_observation`) · `context_id` · `rating` (1–5, o 👍/👎 como
  1/0 en `ai_observation`) · `message` (≤ 1 000) · `page`.
- `product_events`: `user_id` · `name` (lista cerrada) · `props` (solo ids
  y enumerados, nunca texto del alumno) · `occurred_at`. Índice `(name,
  occurred_at)`.
- `error_events`: `request_id` · `route` · `status_code` · `error_code` ·
  `exception_type` · `occurred_at`. Sin mensajes con datos personales;
  retención de 30 días.

**usage** (MVP-02)

- `budget_periods`: `scope` (`global` | `user`) · `scope_key` · `period`
  (`YYYY-MM`) · `limit_microusd` · `reserved_microusd` ·
  `spent_microusd`. Único `(scope, scope_key, period)`.
- `ai_runs`: `user_id` · `purpose` (`writing_feedback` |
  `speaking_feedback` | `transcription` | `voice_session`) · `provider` ·
  `model` · `prompt_version` · `rubric_version` · `attempt_id` ·
  `voice_session_id` · `status` (`reserved` | `running` | `succeeded` |
  `failed` | `unknown` | `released`) · `reserved_microusd` ·
  `observed_units` · `cost_microusd` · `idempotency_key` · `error_code` ·
  `output` (validado).

**coaching** (MVP-02)

- `voice_sessions`: `user_id` · `scenario_revision_id` · `status`
  (`reserved` | `active` | `ended` | `failed` | `expired`) · `deadline_at`
  · `started_at` · `ended_at` · `end_reason` · `aids` · `transcript` (solo
  con consentimiento) · `feedback` · `ai_run_id`. Índice único parcial:
  una sesión `reserved` o `active` por usuario.

**legacy** (congeladas): `courses`, `classes`, `quizzes`, `questions`.
Desde MVP-01 nada las lee ni las escribe; se eliminan en un ciclo posterior
con su propio spec (ADR-08).

## 6. API

Prefijo `/api/v1`, JSON. FastAPI genera el OpenAPI, que se versiona en
`docs/api/openapi.json`; el cliente TypeScript se genera de ese archivo y
la CI falla si alguno de los dos diverge del código (ADR-07).

### 6.1 Convenciones

- Fechas ISO 8601 en UTC; ids opacos; paginación por cursor
  (`?cursor=&limit=`).
- Errores: `{"error": {"code", "message", "request_id"}}`, sin stack
  traces ni secretos. 401 sin sesión · 403 rol, CSRF u Origin · 404
  recurso ajeno o inexistente (indistinguibles) · 409 conflicto
  (idempotencia, hash, estado) · 413 cuerpo grande · 422 validación · 429
  límite con `Retry-After` · 503 capacidad deshabilitada o sin
  presupuesto.
- `Idempotency-Key` (UUID) obligatorio al crear intentos, iniciar o enviar
  comprobaciones y, desde MVP-02, al pedir feedback y crear sesiones de
  voz. Misma clave y mismo cuerpo → misma respuesta; misma clave y cuerpo
  distinto → 409.
- Usuario y rol salen de la sesión. El cuerpo nunca trae `user_id`, rol,
  nota ni modo de comprobación.
- Los DTO del alumno se construyen con lista permitida. Soluciones,
  explicaciones, variantes aceptadas y rúbricas privadas aparecen solo
  después de enviar (práctica) o de cerrar la comprobación.

### 6.2 Endpoints

| Método y ruta | Quién | Propósito y reglas | Ciclo |
|---|---|---|---|
| `POST /auth/invitations/accept` | público | Token de un uso + contraseña + consentimiento + mayoría de edad; crea usuario y sesión | 01 |
| `POST /auth/login` · `POST /auth/logout` | público · sesión | Cookie de sesión y token CSRF; error genérico; logout revoca | 01 |
| `POST /auth/password-reset/confirm` | público | Token de un uso; revoca todas las sesiones | 01 |
| `GET /me` · `PATCH /me` | alumno | Perfil, objetivo y token CSRF; lista explícita de campos editables | 01 |
| `GET /me/export` · `DELETE /me` | alumno | Exportación JSON de sus datos · borrado con confirmación | 01 |
| `GET /learning-paths` · `GET /learning-paths/{id}` | alumno | Solo rutas activas con contenido publicado; unidades, ítems y progreso propio | 01 |
| `GET /lessons/{id}` · `GET /scenarios/{id}` | alumno | Revisión fijada o publicada, sin soluciones | 01 |
| `POST /aids` | alumno | Sirve una ayuda (pista, apoyo en español, transcripción, ejemplo) y la registra; 403 en modo comprobación | 01 |
| `POST /attempts` · `GET /attempts/{id}` · `GET /me/attempts` | alumno | Intento idempotente con corrección en servidor; solo propios | 01 |
| `POST /assessments/{form_id}/start` | alumno | Corrida con orden fijado, sin ayudas | 01 |
| `GET /assessment-runs/{id}` · `PUT /assessment-runs/{id}/answers/{activity_id}` · `POST /assessment-runs/{id}/submit` | alumno | Guardar respuestas sin feedback; cerrar y ver resultados | 01 |
| `GET /me/progress` · `GET /me/reviews` · `GET /me/reviews/next` | alumno | Métricas con denominadores; repasos vencidos y siguiente | 01 |
| `POST /feedback` · `POST /content-reports` | alumno | Feedback del producto · reporte de contenido ligado a revisión | 01 |
| `GET /admin/users` · `POST /admin/invitations` · `POST /admin/users/{id}/reset-link` · `POST /admin/users/{id}/revoke-sessions` | admin | Acceso administrado; enlaces de un uso para entrega manual | 01 |
| `GET /admin/content/revisions` · `GET /admin/content/revisions/{id}` | admin | Lista y detalle completo con vista previa como alumno | 01 |
| `POST /admin/content/revisions/{id}/findings` · `PATCH /admin/content/findings/{id}` | admin | Hallazgos editoriales | 01 |
| `POST /admin/content/revisions/{id}/approve` · `…/publish` · `…/withdraw` | admin | Aprobar por hash; publicar atómico; retirar sin borrar historial | 01 |
| `GET /admin/pilot/summary` · `GET /admin/feedback` · `GET /admin/content-reports` · `PATCH /admin/content-reports/{id}` · `GET /admin/errors` | admin | Panel del piloto | 01 |
| `GET /health` (sin prefijo) · `GET /ready` | público | Liveness sin base de datos · readiness con `SELECT 1` y migración en head | 01 |
| `POST /attempts/{id}/feedback` | alumno | Feedback abierto con IA, validado o "no evaluable" | 02 |
| `POST /speaking/transcriptions` | alumno | Audio ≤ 60 s en memoria → transcripción; el audio no se guarda | 02 |
| `POST /voice-sessions` · `WS /ws/voice/{id}` · `POST /voice-sessions/{id}/stop` · `GET /voice-sessions/{id}` · `POST /voice-sessions/{id}/turns/{n}/flag` | alumno | Coach de voz con límites del servidor | 02 |
| `GET /admin/usage` | admin | Consumo y costo por periodo y alumno | 02 |

Estáticos: `/assets/*` (build con hash, caché inmutable), `/media/*`
(audio del contenido) y fallback de la SPA solo para `GET` con `Accept:
text/html` fuera de `/api`, `/ws`, `/media`, `/assets` y `/health`. Un 404
de la API es JSON; un asset inexistente es 404, nunca `index.html`.

En `APP_ENV=test` existe `POST /api/test/clock` para mover el reloj en los
E2E. La app se niega a arrancar si esa ruta queda activa con
`APP_ENV=prod`.

## 7. Seguridad (regla 9)

**Authn — sesiones opacas en PostgreSQL** (ADR-04). Token de 32 bytes
aleatorios; se guarda solo su sha256. Cookie `__Host-pcre_session`:
`HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`, sin `Domain`. Vencimiento
absoluto de 7 días e inactividad de 24 h (configurables). Se rota al
iniciar sesión y se revoca al cerrar sesión, al consumir un reset y al
borrar la cuenta. `last_seen_at` se actualiza como máximo cada 5 minutos.
Nunca hay tokens en `localStorage`.

**CSRF y Origin.** Token CSRF por sesión (se guarda su hash), entregado por
`login` y `GET /me`, enviado en `X-CSRF-Token` en todo método no seguro y
comparado en tiempo constante. Además, `Origin` (o `Referer`) debe estar en
`APP_ORIGIN` o en la lista de desarrollo. El WebSocket valida `Origin` antes
de `accept()`: el `CORSMiddleware` de Starlette no cubre el handshake
`[inherited: lección de CareerAI, NFR-04 de C2-SPEC-01]`.

**Authz.** Usuario y rol siempre desde la sesión. Todo recurso de alumno se
filtra por `user_id` en el repositorio; un recurso ajeno responde 404. Las
rutas `/admin/*` exigen `role=admin`. El primer admin solo se crea por CLI
(`app.cli create-admin-invite`), en un one-off dyno que ejecuta Jonathan.

**Contraseñas.** Argon2id con `argon2-cffi` y sus parámetros por defecto;
mínimo 10 caracteres y máximo 128, sin reglas de composición; se rechaza la
igual al email. Sin criptografía propia.

**Abuso.** Límite de intentos de login por email e IP (5 por minuto, 20 por
hora) en memoria del proceso (trigger del §2 para moverlo a la base de
datos). Límite de cuerpo: 64 KB en JSON y 2 MB en audio (MVP-02). Texto
libre del alumno: máximo 4 000 caracteres.

**Cabeceras.** `Content-Security-Policy` con `default-src 'self'`,
`script-src 'self'`, `style-src 'self'`, `img-src 'self' data:`,
`media-src 'self' blob:`, `connect-src 'self'` más el origen `wss:` propio,
`font-src 'self'`, `frame-ancestors 'none'`, `object-src 'none'`,
`base-uri 'self'`. También HSTS (en producción), `X-Content-Type-Options:
nosniff`, `Referrer-Policy: strict-origin-when-cross-origin` y
`Permissions-Policy: microphone=(self), camera=(), geolocation=()`. Las
fuentes tipográficas se sirven desde la app (sin CDN de terceros).

**Contenido.** Markdown renderizado sin HTML crudo. El texto del alumno
nunca se interpreta como HTML ni como instrucciones para un modelo
(§8).

**Secretos.** Solo en Heroku Config Vars y en secrets de environments de
GitHub. En el repo, placeholders. La CI busca llaves y endpoints de
proveedores en el bundle del frontend y falla si los encuentra.

**Logs.** Una línea JSON por evento con `ts`, `level`, `msg`,
`request_id`, `route`, `status`, `duration_ms` y `user_ref` (hash corto y
salado del id). Nunca contraseñas, tokens, cookies, cabeceras
`Authorization`, emails completos, respuestas del alumno, transcripciones
ni audio.

**Datos personales.** Aviso de privacidad visible antes de recolectar
datos, con consentimiento versionado y acreditación de mayoría de edad (el
piloto es solo para adultos). Exportación y borrado en la app (acceso y
cancelación). Marco: la Ley Federal de Protección de Datos Personales en
Posesión de los Particulares publicada en el DOF el 20 mar 2025, en vigor
desde el 21 mar 2025 `[verified-this-session: resumen de KPMG México]`.
El texto legal es un borrador que Jonathan revisa; este documento no es
asesoría legal.

## 8. Integraciones externas (regla 6)

Toda integración vive detrás de un puerto con un doble de prueba. La CI y
las pruebas locales bloquean conexiones a hosts reales de proveedores: una
llamada real falla la suite.

| Proveedor y uso | Puerto | Timeout y reintentos | Degradación | Costo de referencia |
|---|---|---|---|---|
| Google Gemini (`google-genai`): feedback abierto (MVP-02) | `FeedbackEvaluator` | 20 s total (bajo los 30 s del router de Heroku); sin reintento automático si el resultado es desconocido | Rúbrica de autoevaluación identificada como tal | Modelo por `GEMINI_MODEL`; precio por `GEMINI_PRICE_*` |
| Deepgram Voice Agent (`wss://agent.deepgram.com/v1/agent/converse`): coach de voz (MVP-02) | `VoiceAgent` | Conexión 5 s; `KeepAlive`; sin reconexión a media sesión: se cierra con aviso | Modo texto del mismo escenario | USD 0.075/min estándar con STT, LLM y TTS incluidos `[verified-this-session: deepgram.com/pricing, 5 oct 2026]` |
| Deepgram Nova-3 pregrabado: transcripción de grabaciones (MVP-02) | `SpeechToText` | 15 s; sin reintento | Autoevaluación | USD 0.0043/min monolingüe `[verified-this-session]` |
| Deepgram Aura-2 TTS: audio del contenido (workflow, no en runtime) | `TextToSpeech` | Por segmento; reintento acotado en el workflow | El contenido sin audio revisado no se publica | USD 0.030 por 1 000 caracteres `[verified-this-session]` |

Reglas comunes:

- El texto del alumno y los documentos externos se tratan como datos:
  delimitados en el prompt, sin herramientas, sin acceso a secretos y sin
  capacidad de publicar, conceder progreso ni cambiar permisos.
- La salida de un modelo se valida con esquema antes de guardarse. Toda
  observación cita un fragmento literal de la respuesta del alumno; si el
  fragmento no existe, la observación se descarta. Sin observaciones
  válidas, el resultado es "no evaluable".
- Una ejecución facturable de resultado desconocido nunca se repite
  automáticamente.
- Modelos, precios y versiones van en configuración, no en código.
  CareerAI usa `google-genai` y `gemini-3.1-flash-lite`, con apagado
  anunciado para el 7 may 2027 `[inherited: HANDOFF de CareerAI @ 0db81a1]`;
  el modelo de PCRE se elige con el set de evaluación de MVP-02.
- **Cuentas separadas de CareerAI:** proyecto y llave propios en Deepgram y
  en Google para no compartir saldo, cuotas ni atribución de costos (regla
  10).

## 9. Presupuesto y consumo (MVP-02, ADR-11)

- Sin presupuesto configurado, toda capacidad con costo queda
  **deshabilitada** (fail-closed) y la interfaz ofrece la alternativa
  gratuita.
- Antes de cada llamada se **reserva** el costo máximo autorizado
  (tokens máximos o segundos máximos × precio) en una transacción que
  bloquea con `SELECT … FOR UPDATE` la fila global y después la del alumno
  (orden fijo para evitar deadlocks). Si alguna excede su límite, se
  rechaza con 503 y un mensaje claro.
- Al terminar se **concilia** lo observado (reservado → gastado, sobrante
  liberado). Una ejecución interrumpida queda `unknown` y conserva la
  reserva completa: no se asume consumo cero.
- La concurrencia de voz se controla en la base de datos: índice único
  parcial por alumno y un lock consultivo para el cupo global.
- Topes duros fuera de la app: saldo prepagado de Deepgram con
  **Auto-reload apagado** `[inherited: dictamen C2-D2 de CareerAI]` y
  límite de gasto en la facturación de Google.

## 10. Frontend (ADR-06)

- React + Vite + TypeScript estricto en `apps/frontend/`. React Router en
  modo librería, TanStack Query para el estado del servidor, cliente
  `openapi-fetch` con tipos de `openapi-typescript` generados desde
  `docs/api/openapi.json`, `react-markdown` sin HTML crudo.
- CSS Modules con tokens en variables CSS (`src/styles/tokens.css`); sin
  kit de componentes. Elementos HTML nativos primero (radios, botones,
  `dialog`, `details`), que ya son accesibles.
- Textos de la interfaz en español centralizados (`src/i18n/es.ts`); el
  material de práctica, en inglés.
- Estructura: `src/app/` (router, layout, proveedores), `src/pages/`,
  `src/features/<dominio>/` (componentes y hooks por dominio),
  `src/components/` (primitivas), `src/api/` (cliente generado + wrapper),
  `src/styles/`, `src/i18n/`.
- Navegadores: Safari iOS y Chrome Android (dos últimas versiones), Chrome
  y Edge de escritorio (dos últimas); Firefox de escritorio con mejor
  esfuerzo en voz. Diseño mobile-first.
- Accesibilidad: WCAG 2.2 AA en los flujos principales; teclado, foco
  visible, etiquetas, contraste y `prefers-reduced-motion`.
- La dirección visual (paleta, tipografía, composición) está en MVP-01
  §"Dirección visual".

## 11. Despliegue y CI/CD (ADR-13)

```
GitHub (repo público)
 ├─ PR ──► ci.yml: backend · migrations · frontend · contract · content · e2e · image ──► ci-gate
 ├─ merge a main (CI verde, ruleset) ──► deploy.yml
 │                                         └─ environment "production": aprobación de Jonathan
 │                                              ├─ backup de la base si hay migraciones nuevas
 │                                              ├─ git push a Heroku (build Docker remoto)
 │                                              └─ smoke: /health · /api/v1/ready · /
 └─ workflow_dispatch: content-audio.yml (TTS) · feedback-eval.yml (MVP-02), con environment aprobado

Heroku app (Cedar, stack container, 1 web dyno)
 ├─ release: alembic upgrade head && importación de contenido (solo borradores)
 └─ web: uvicorn app.main:app, 1 worker, $PORT, proxy headers, límites de WebSocket
       └─ Heroku Postgres Essential-0
```

- **Imagen:** `Dockerfile` multietapa en la raíz (Node 22 compila el
  frontend; Python 3.12-slim con `curl` y `uv` ejecuta el backend). La
  imagen necesita `curl` para que Heroku transmita los logs de la release
  phase `[verified-this-session: devcenter heroku.yml]`.
- **`heroku.yml`:** `build.docker.web`, `release` (`image: web` y comando
  de migración e importación) y `run.web` con `uvicorn … --host 0.0.0.0
  --port $PORT --workers 1 --proxy-headers --forwarded-allow-ips '*'
  --ws-max-size 1048576 --ws-max-queue 8 --ws-per-message-deflate false`.
  Los tres últimos flags vienen de la revisión de memoria de CareerAI
  `[inherited: heroku.yml de CareerAI @ 0db81a1]`. Si la release phase
  falla, Heroku no promueve la release.
- **Límites de Heroku:** 30 s al primer byte (H12), ventana rodante de
  55 s en conexiones abiertas, 512 MB de RAM, sistema de archivos efímero
  `[inherited: spec de migración de CareerAI]`.
- **CI (`ci.yml`)** en cada PR y push a `main`, con `permissions:
  contents: read` y sin secretos. El job `ci-gate` depende de todos los
  demás y es el **único check requerido** por el ruleset de `main`: así los
  jobs pueden cambiar sin tocar la configuración del repo. Nunca se
  renombra ni se elimina.
- **CD (`deploy.yml`):** corre tras un CI verde en `main`, en el
  environment `production` con revisor obligatorio (Jonathan). Si hay
  migraciones nuevas captura un backup antes del push. Sin
  `HEROKU_API_KEY` el job termina con un mensaje explícito, nunca en verde
  falso.
- **Rollback:** `heroku rollback -a <app>` regresa código y comando de
  arranque; las migraciones expand mantienen compatible el esquema. El
  contenido se revierte retirando una revisión o republicando la anterior.
- **Backups:** programación diaria de PG Backups y captura manual antes de
  cada deploy con migraciones; ensayo de restauración en una base desechable
  antes de invitar alumnos (runbook).

## 12. Observabilidad

- Logs JSON a stdout (`heroku logs`). Heroku guarda pocas líneas, por eso
  los errores 5xx también se registran en `error_events` (sin datos
  personales) y aparecen en el panel del piloto.
- `GET /health` comprueba el proceso; `GET /api/v1/ready` comprueba la base
  de datos y que la migración aplicada sea el head esperado, sin depender
  de proveedores de IA.
- Panel del piloto: alumnos activos por día, intentos, lecciones completadas,
  repasos, valoraciones, comentarios, reportes de contenido, errores y,
  desde MVP-02, minutos de voz y costo.
- Sentry u otro rastreador externo: diferido (ADR-14).

## 13. Entorno del agente de desarrollo

Sesiones cloud de Claude Code `[verified-this-session:
code.claude.com/docs/en/cloud-environments, 5 oct 2026]`:

- VM Ubuntu 24.04 con Python 3 (pip, uv, pytest, ruff, mypy), Node 20/21/22
  (22 en `PATH`), Docker y PostgreSQL 16 y Redis 7 instalados pero
  apagados (`service postgresql start`). Límite aproximado: 4 vCPU, 16 GB
  de RAM y 30 GB de disco.
- Red **Trusted**: PyPI, npm, GitHub, Docker Hub, `mcr.microsoft.com` y los
  repositorios de Ubuntu. Heroku y Deepgram no están en la lista: la sesión
  no puede desplegar ni llamar a Deepgram aunque lo intente. La descarga de
  navegadores de Playwright no está en la lista; el E2E con navegador corre
  en la CI (o con la imagen de Playwright de `mcr.microsoft.com`).
- Comandos: 2 minutos por defecto y hasta 10 (`BASH_DEFAULT_TIMEOUT_MS` y
  `BASH_MAX_TIMEOUT_MS` en el environment). La VM se pausa cuando la sesión
  queda inactiva.
- GitHub por proxy: `git push` a ramas y la API REST con `gh api`. GraphQL
  no está disponible, así que `gh pr create` falla: los PR se abren por REST
  `[verified-this-session: proxy de esta sesión]`.
- Setup: `.claude/settings.json` (reglas `deny` desde G0; hook
  `SessionStart` desde MVP-01 CS-1) + `scripts/dev/cloud-session-start.sh`,
  que sale de inmediato si `CLAUDE_CODE_REMOTE` no es `true`.

## 14. Decisiones (ADR)

Cada decisión: qué ganas · qué pagas · alternativas · cuándo revisarla.

**ADR-01 · Monolito modular por módulos con puertos selectivos.** Ganas:
una unidad de despliegue, reglas probables sin FastAPI, base de datos ni
IA, y proveedores sustituibles. Pagas: interfaces, mapeos y disciplina en
los límites (vigilada por import-linter). Descartado: reglas dentro de
endpoints y ORM (no se prueban sin infraestructura) y microservicios (no
hay equipos ni escalado separado). Revisar si un módulo necesita escalar o
desplegarse aparte.

**ADR-02 · Exámenes, niveles y rutas como datos versionados.** Una ruta
declara examen, versión de formato, niveles orientativos, objetivos,
familias de tareas y rúbricas; cada intento apunta a la revisión exacta.
Ganas: agregar IELTS o B2 First sin duplicar identidad, progreso ni
persistencia. Pagas: un esquema de contenido más rico. Descartado: un
condicional por examen en cada controlador y un motor universal de
plugins. Solo una ruta activa en el MVP.

**ADR-03 · Contenido como código; estado editorial en la base de datos.**
Los borradores son YAML en `content/` (revisables en PR, con lint y
cobertura en CI). La importación crea revisiones `draft` idempotentes por
hash; aprobar, publicar y retirar ocurre en el panel y queda auditado en la
base de datos. Ganas: diffs legibles, trabajo del agente en archivos y
publicación solo humana. Pagas: dos lugares que reconciliar (el hash los
une). Descartado: editor visual en la app (fuera del MVP) y contenido solo
en base de datos (sin revisión por PR).

**ADR-04 · Sesiones opacas en PostgreSQL, no JWT.** Ganas: logout y reset
con revocación inmediata y un modelo de amenaza simple. Pagas: una
consulta por petición (índice por hash) que no escala horizontalmente sin
la misma base, algo irrelevante con un dyno. Descartado: JWT en cookie (la
revocación exige lista negra) y tokens en `localStorage`.

**ADR-05 · SQLAlchemy síncrono con psycopg 3.** Ganas: sin los problemas
de carga perezosa del modo async y patrones conocidos por el agente. Pagas:
el threadpool limita la concurrencia (suficiente para 10 peticiones
concurrentes). El WebSocket hace sus pocas operaciones de base de datos
fuera del event loop. Descartado: SQLAlchemy async con asyncpg (más
superficie de error sin beneficio medido).

**ADR-06 · React + Vite + TypeScript servido por FastAPI.** Sustituye la
intención antigua de Next.js, que nunca se implementó. Ganas: un solo
runtime en producción, mismo origen para cookies y WebSocket, y el patrón
que ya funciona en CareerAI. Pagas: sin SSR (no hace falta para un panel
autenticado). Descartado: Next.js (segundo servidor Node sin necesidad).

**ADR-07 · Contrato API generado.** OpenAPI versionado y tipos TypeScript
generados, con verificación de drift en CI. Ganas: el frontend no se
desincroniza en silencio. Pagas: un paso de generación por cambio de
esquema. Descartado: interfaces escritas a mano (CareerAI lo hace con una
API pequeña; aquí la API es cuatro veces más grande).

**ADR-08 · Tablas nuevas para el currículo; tablas legadas congeladas.**
`courses`/`classes`/`quizzes`/`questions` modelan un apunte con quiz, no
rutas versionadas con revisiones, pools y comprobaciones. Ganas: nombres y
restricciones correctos desde el inicio. Pagas: tablas legadas sin uso
hasta su retiro. Como no hay producción ni datos reales, no se pierde nada;
el contenido legado se conserva como referencia en `content/_legacy/` con
la regla de comparativos corregida. Descartado: reinterpretar `courses`
como unidad y `classes` como lección (propuesta del contrato
PCRE-MVP-20261005 §7), que arrastra `has_quiz`, `markdown_content` y
`options` como texto.

**ADR-09 · Corrección cerrada determinista; IA solo para lo abierto.**
Selección, completado y orden se corrigen en el servidor sin modelos. El
feedback abierto se pide después de guardar la respuesta, con salida
estructurada, evidencia literal obligatoria y abstención. Ganas:
resultados reproducibles, cero costo en lo cerrado y confianza en el
feedback. Pagas: el feedback abierto llega en una segunda petición.

**ADR-10 · Voz por relay del backend.** El navegador habla solo con la app;
el backend abre la conexión con Deepgram, aplica el deadline y concilia el
consumo. Los tokens breves de Deepgram solo limitan el inicio de una
conexión, no cortan una llamada abierta (spec de producto v0.3 §12), así
que el límite de 5 minutos lo impone el servidor. Ganas: la llave nunca
llega al navegador y el corte es real. Pagas: el audio pasa por el dyno
(suficiente para 3 sesiones). Descartado: conexión directa del navegador.

**ADR-11 · Presupuestos fail-closed con reservas atómicas.** Ver §9. Ganas:
dos peticiones simultáneas no rebasan el tope. Pagas: una transacción con
bloqueo por llamada facturable.

**ADR-12 · Audio del contenido pregenerado y versionado.** El TTS corre en
un workflow manual aprobado (llave en un environment de GitHub, tope de
caracteres) y abre un PR con los MP3 y su manifiesto de procedencia. Ganas:
audio persistente y revisable, costo único y ninguna llave en la sesión del
agente. Pagas: binarios en Git (trigger a object storage en el §2).
Descartado: TTS en tiempo de ejecución (costo por reproducción y fallas en
vivo) y archivos en el disco efímero del dyno.

**ADR-13 · CI/CD con GitHub Actions y deploy aprobado.** Ganas: el deploy
no depende de la Mac de Jonathan, se aprueba con un clic (también desde el
teléfono) y queda registrado; los checks protegen `main`. Pagas: una llave
de Heroku guardada como secret del environment. Descartado: `git push
heroku main:main` manual (el flujo actual de CareerAI) y deploy automático
sin aprobación con usuarios reales.

**ADR-14 · Observabilidad propia mínima.** Logs JSON + `error_events` +
panel. Ganas: sin otro proveedor que procese datos personales. Pagas: sin
agrupación de errores ni alertas. Revisar al pasar de 10 alumnos externos:
evaluar Sentry con limpieza de datos personales.

**ADR-15 · Toolchain.** Python 3.12 con `uv` (`pyproject.toml` +
`uv.lock`); Node 22 con npm (`package-lock.json`); ruff y mypy en el
backend, `tsc` y ESLint en el frontend. Ganas: coincide con la VM cloud
(Ubuntu 24.04) y con CareerAI, y deja builds reproducibles. Pagas:
actualizar Node antes de abril de 2027 (fin de soporte de la versión 22).

## 15. Sistemas adyacentes (regla 10)

| Sistema | Cómo lo afecta este diseño |
|---|---|
| Router y dynos de Heroku | Timeouts de 30 s y 55 s, 512 MB, FS efímero, `$PORT`, SIGTERM con 30 s para cerrar: feedback con timeout de 20 s, keepalive en el WebSocket, nada en disco, apagado ordenado |
| Heroku Postgres Essential-0 | 20 conexiones: pool de 5 + 5; sin rollback: backups antes de migrar |
| GitHub Actions | Minutos gratuitos en repo público; E2E con navegador solo aquí |
| Sesión cloud del agente | Sin Heroku ni Deepgram; red Trusted; trabajo verificable sin llaves |
| Cuentas de Deepgram y Google | Separadas de CareerAI; saldo prepagado y límites de gasto |
| Navegadores móviles | Permiso de micrófono, `AudioContext` que requiere un gesto, audio en segundo plano |
| CareerAI | Fuente de patrones (relay, Deepgram falso, Origin, flags de uvicorn, CI con arranque de imagen), sin dependencia en tiempo de ejecución |

---

## Enmiendas

Ninguna todavía.
