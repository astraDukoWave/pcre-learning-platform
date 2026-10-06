# HANDOFF.md — PCRE Learning Platform

> Fuente de verdad para cualquier sesión que tome este proyecto.
> Se sobrescribe al cerrar cada fase; no se acumula.

---

## 1. Identidad del proyecto

- **Producto:** SaaS de práctica de inglés B1 → B2 para hispanohablantes
  que lo necesitan para trabajo o estudios. Primera ruta:
  `toefl-ibt-2026-b1-b2` (tareas tipo TOEFL iBT, formato 2026), como
  preparación independiente y formativa.
- **Repo:** https://github.com/astraDukoWave/pcre-learning-platform —
  **PÚBLICO** (portafolio).
- **Producción:** aún no existe. Destino: Heroku, una app Cedar con stack
  `container`, un dyno web Basic y Heroku Postgres Essential-0. `deploy.yml` está en
  `main`, apagado hasta que Jonathan firme G1 (pasos en `docs/runbook.md`).
- **Nombre:** "PCRE" (Pattern, Concept, Rules, Examples) es el nombre del
  método de explicación y el nombre de trabajo; el nombre comercial está
  abierto (LB-05). `APP_NAME` lo deja configurable.
- **Fase actual:** MVP-01 **cerrado** el 6 oct 2026 (verify ✅ y dictamen de activación
  G1–G4 en `docs/reviews/`); MVP-02 en ejecución en la misma sesión cloud con `/goal`.
  Gates G1–G4 sin iniciar: dependen de Jonathan.

## 2. Estado real

### ✅ Existe (verificado el 6 oct 2026 sobre `main` @ `4df036c`)

| Qué | Evidencia |
|---|---|
| Base reproducible: Python 3.12 + uv, Node 22, `make verify`, hook de arranque cloud | `make verify` exit 0 en un clon limpio tras el hook `[verified-this-session]` |
| CI con 8 jobs + `ci-gate` (backend, migrations, content, frontend, contract, e2e, image, workflows) | Run [37413020925](https://github.com/astraDukoWave/pcre-learning-platform/actions/runs/37413020925) `[ci-run]` |
| Identidad: invitaciones, sesiones opacas, CSRF, reset, exportación y borrado | `tests/identity/` `[ci-run]` |
| Contenido como código con lint, cobertura, paquete de revisión y flujo editorial por hash | `tests/content/`, `docs/contenido/revision/` `[ci-run]` |
| Práctica: seis formatos, ayudas, autoevaluación, comprobaciones, repaso 1/3/7 y progreso | `tests/practice/`, `tests/progress/`, E2E `[ci-run]` |
| Panel editorial, reportes, feedback y panel del piloto | `tests/insights/`, `e2e/test_publishing.py` `[ci-run]` |
| Seguridad (§7), accesibilidad (axe, teclado, teléfono) y rendimiento (p95 < 800 ms) | `docs/reviews/mvp-01-seguridad.md`, `e2e/test_accessibility.py`, `docs/reviews/mvp-01-perf-smoke.md` |
| U1 (4 lecciones, escenario, checkpoint) y diagnóstico inicial en `ready-for-review` | `docs/contenido/revision/{u1,inicial}.md`; lint 0 errores |
| `deploy.yml` aprobado y apagado; `content-audio.yml` aprobado | Runs de deploy `skipped` en `main` `[verified-this-session]` |

### ⏸ Pendiente (humano)

| Qué | Dónde |
|---|---|
| H-1b: `ci-gate` como check requerido del ruleset | Plan de MVP-01, "Tareas [HUMANO]" |
| G1 deploy · G2 audio · G3 publicación · G4 alumnos reales | `docs/reviews/mvp-01-activacion-cto-review.md` y `docs/runbook.md` |
| H-6 prueba en iPhone y Android | `docs/runbook.md` §12 |
| Fuentes de Cambridge y del Consejo de Europa sin consultar (la sesión no llega a esos hosts) | `content/toefl-ibt-2026-b1-b2/sources.yaml`; se confirman en G3 |

## 3. Arquitectura

Resumen de `docs/arquitectura.md`: monolito modular (FastAPI + PostgreSQL)
que sirve API, WebSocket (MVP-02), audio y la SPA de React; un dyno en
Heroku; CI en GitHub Actions con `ci-gate` como único check requerido;
deploy desde GitHub Actions con aprobación del environment `production`.

```
Navegador (React SPA) ── same origin ──► Heroku web dyno (uvicorn, 1 worker)
                                          ├─ /api/v1 · /ws (MVP-02) · /media · /assets
                                          ├─ release: alembic upgrade head + importación de contenido
                                          └─ Heroku Postgres Essential-0
Proveedores (MVP-02, apagados hasta G5): Gemini (feedback) · Deepgram (voz, STT)
Workflows aprobados: deploy.yml (G1) · content-audio.yml (G2) · feedback-eval.yml (G5a)
```

## 4. Decisiones técnicas (cerradas en G0, 5 oct 2026)

| Decisión | Elegido | Razón | Dónde |
|---|---|---|---|
| Forma | Monolito modular por módulos con puertos selectivos | Una unidad de despliegue; reglas probables sin infraestructura | ADR-01 |
| Rutas y exámenes | Datos versionados; una ruta activa | Agregar exámenes sin duplicar el núcleo | ADR-02 |
| Contenido | YAML en el repo; estado editorial en la base | Diffs revisables; publicación solo humana | ADR-03 |
| Sesiones | Opacas en PostgreSQL, cookie `__Host-` | Revocación inmediata | ADR-04 |
| Base de datos | SQLAlchemy 2 síncrono + psycopg 3 + Alembic expand | Menos superficie de error | ADR-05 |
| Frontend | React + Vite + TS servido por FastAPI | Un runtime, mismo origen | ADR-06 |
| Contrato | OpenAPI versionado + tipos generados | Sin drift silencioso | ADR-07 |
| Currículo | Tablas nuevas; legadas congeladas | Nombres y restricciones correctas | ADR-08 |
| IA | Cerrado determinista; abierto con evidencia literal | Reproducible y confiable | ADR-09 |
| Voz | Relay en el backend con deadline del servidor | La llave no sale; el corte es real | ADR-10 |
| Costo | Reservas atómicas y fail-closed | Topes que resisten concurrencia | ADR-11 |
| Audio | TTS en workflow aprobado; MP3 versionados | Costo único y revisable | ADR-12 |
| CI/CD | GitHub Actions + deploy aprobado | No depende de la Mac; un clic | ADR-13 |
| Observabilidad | Logs JSON + `error_events` | Sin otro procesador de datos | ADR-14 |
| Toolchain | Python 3.12 + uv · Node 22 + npm | Coincide con la VM cloud y CareerAI | ADR-15 |
| Merges | Claude mergea con merge commit (delegado en G0 para MVP-01 y MVP-02); Jonathan aprueba deploys | Autonomía con gate en producción | G0 |
| Dyno | Basic | Sin sueño para los primeros clientes | G0, decisión 3 |

## 5. Estrategia comercial — fuera del repo

Clientes, créditos, precios, competidores e hipótesis de negocio viven en
`strategy.md`, documento privado del Proyecto "English StartUp" en Claude,
junto con el discovery (contrato PCRE-MVP-20261005 y spec de producto
v0.3). Nada de eso entra al repo; los specs lo citan por nombre.

## 6. Roadmap

1. **MVP-01 · Núcleo y piloto U1** (`docs/specs/mvp-01-nucleo-piloto.md`):
   plataforma, CI/CD, Unidad 1, diagnóstico. Tras su activación (G1–G4),
   los primeros clientes empiezan.
2. **MVP-02 · Coach con IA y voz** (`docs/specs/mvp-02-coach-ia-voz.md`):
   feedback con evidencia, transcripción y coach de voz, apagados hasta G5.
3. **MVP-03 · Ruta completa** (`docs/specs/mvp-03-ruta-completa.md`):
   unidades 2–8 y formulario final, tras G6.
4. **Después:** lo que decidan las métricas del piloto (Learning Backlog).

### Learning Backlog (única lista de oportunidades)

- **LB-01 · Ruta "inglés para entrevistas técnicas".** `[hipótesis]` Los
  desarrolladores de la región que aplican a empresas con entrevistas en
  inglés son un mercado cercano a la red de Jonathan, y el coach de voz y
  CareerAI ya cubren parte del camino. Validación: conversación con 5
  desarrolladores antes de construir.
- **LB-02 · Segunda ruta de examen** (IELTS Academic, después Cambridge B2
  First). Trigger: 3 alumnos o más con esa meta registrada en su perfil.
- **LB-03 · B2 → C1 y C1 → C2.** Después de completar la primera ruta.
- **LB-04 · Revisión editorial asistida** (búsqueda con grounding o un
  modelo con fuentes que proponga hallazgos, nunca aprobaciones). Trigger:
  más de 2 h de revisión por unidad.
- **LB-05 · Nombre comercial, dominio y landing con lista de espera.**
  "PCRE" choca en buscadores con la librería de expresiones regulares.
- **LB-06 · Pagos y planes** (suscripción con minutos de voz incluidos).
  Trigger: 5 alumnos activos durante 4 semanas y costo por alumno medido.
- **LB-07 · Oferta para escuelas** (coach como servicio, multi-institución).
  Trigger: una escuela interesada.
- **LB-08 · Registro abierto y email transaccional.** Trigger de
  `docs/arquitectura.md` §2.
- **LB-09 · Contenido y claves fuera del repo público.** Antes de abrir el
  registro.
- **LB-10 · "Constancia de práctica" exportable** que no parezca un
  certificado. Validar primero con los primeros clientes si su institución
  la valoraría.
- **LB-11 · Retiro de las tablas legadas** (spec propio).
- **LB-12 · Tema oscuro.**
- **LB-13 · Rastreador de errores externo** (ADR-14). Trigger: más de 10
  alumnos externos.
- **LB-14 · Recordatorios** (correo o mensajería). Trigger: uso recurrente
  menor a 2 días por semana.

## 7. Metodología

- Claude trabaja como CTO y ejecutor en una sola ventana; las ejecuciones
  largas corren en una sesión cloud de Claude Code con `/goal`.
  Procedimiento: `docs/sdd/proceso.md`.
- Ciclo: `brainstorm → design-spec (+ system-design-spec) → design-plan →
  ejecución → verify → cto-review → release`. Skills v0.3:
  `workflow-router`, `design-plan`, `verify`; v0.2: `brainstorm`,
  `design-spec`, `system-design-spec`, `cto-review`. Viven en la cuenta de
  Claude, no en el repo.
- **Jonathan** aprueba specs, planes y ratificaciones; firma G0–G6; maneja
  secretos; aprueba deploys; publica contenido; invita personas; hace las
  pruebas con navegador real, micrófono y teléfono.
- **Evidencia:** CI ligada al SHA > output en la sesión > diff > reporte.
- **Reglas fijas:** nada vive solo en el working tree; todo cambio a `main`
  pasa por PR; ningún "listo" sin verificación contra el repo real.

## 8. Archivos clave

| Archivo | Propósito |
|---|---|
| `HANDOFF.md` | Fuente de verdad entre fases |
| `STATE.md` | Ciclo activo, gates, registro de change sets, desviaciones |
| `CLAUDE.md` · `AGENTS.md` | Reglas del agente · guía para cualquier agente |
| `docs/sdd/proceso.md` | Procedimiento y plantillas del flujo SDD |
| `docs/arquitectura.md` | Escala, módulos, datos, API, seguridad, CI/CD, ADRs |
| `docs/contenido/contrato-curricular.md` | Reglas del contenido de la ruta |
| `docs/specs/` · `docs/plans/` | Un spec y un plan por ciclo |
| `docs/reviews/` | Dictámenes `cto-review` y reportes `verify` |
| `.claude/settings.json` | Reglas `deny` del agente y hook de arranque |
| `docs/runbook.md` | Operación: Heroku, GitHub, deploy, rollback, restauración, audio, publicación, invitaciones |
| `docs/contenido/revision/` | Paquetes de revisión por unidad (`make review-packet UNIT=u1`) |

## 9. Variables de entorno (solo placeholders — repo público)

```bash
# Runtime (Heroku Config Vars o .env local, ignorado por git)
DATABASE_URL=<Heroku la provee>
APP_ENV=prod
APP_NAME=PCRE
APP_ORIGIN=https://<app>.herokuapp.com
LOG_SALT=<valor aleatorio>
CONSENT_VERSION=<versión aprobada del aviso de privacidad>
PRIVACY_CONTACT_EMAIL=<correo de contacto>
# MVP-02 (apagadas hasta G5)
AI_FEEDBACK_ENABLED=false
STT_ENABLED=false
VOICE_ENABLED=false
GEMINI_API_KEY=<Heroku Config Vars>
GEMINI_MODEL=<elegido con el set de evaluación>
DEEPGRAM_API_KEY=<Heroku Config Vars, proyecto propio de PCRE>
BUDGET_GLOBAL_MONTHLY_MICROUSD=25000000   # USD 25 al mes (G0)
BUDGET_USER_MONTHLY_MICROUSD=8000000      # USD 8 por alumno al mes (G0)
VOICE_MAX_MINUTES_PER_USER_MONTH=60       # (G0)

# GitHub (Settings → Environments / Variables)
# environment production: secret HEROKU_API_KEY (con revisor obligatorio)
# variables del repo: HEROKU_APP_NAME, DEPLOY_ENABLED
# environment content-audio: secret DEEPGRAM_API_KEY
# environment evals: secret GEMINI_API_KEY
```

## 10. Próxima sesión — cola

1. MVP-02 CS-01 → … → CS-08 en la sesión cloud en curso (`/goal`); su cierre deja
   `docs/reviews/mvp-02-verify.md` y `docs/reviews/mvp-02-activacion-cto-review.md`.
2. Jonathan: H-1b y después G1 → G2 → G3 → G4 con el dictamen de MVP-01 y el runbook.
3. G5/G5a (IA y voz) solo después de G4 y con el dictamen de MVP-02.
4. G6 (MVP-03) cuando U1 esté revisada y el examen de los primeros clientes confirmado.

---

*Última actualización: 6 oct 2026 (cierre de MVP-01).*
