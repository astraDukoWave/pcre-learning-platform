# Verify — MVP-01 · Núcleo y piloto U1

- **Spec:** `docs/specs/mvp-01-nucleo-piloto.md` @ `9aa2e2c` · **Plan:**
  `docs/plans/mvp-01-nucleo-piloto-plan.md` @ `0100c0a`.
- **Código verificado:** `main` @ `4df036c` (merge de CS-11, PR #13). CS-12 solo agrega
  documentos.
- **Fecha:** 6 oct 2026. Formato: skill `verify` según `docs/sdd/proceso.md` §9.
- **Verificador independiente:** subagente de contexto fresco con spec, diff
  `a642934...4df036c` y evidencia (sección 6).
- **Etiquetas:** `[ci-run]` run ligado al SHA · `[verified-this-session]` output en la
  sesión · `[inherited-unverified]` · `[contradicted]`.

## Evidencia base

- **CI de `main` @ `4df036c`:** run
  [37413020925](https://github.com/astraDukoWave/pcre-learning-platform/actions/runs/37413020925)
  ✅ `backend`, `migrations`, `content`, `frontend`, `contract`, `e2e`, `image`, `workflows`
  y `ci-gate` `[ci-run]`. Cada PR de MVP-01 tiene su run en verde en el registro de
  `STATE.md`.
- **`make verify` en un clon limpio** de `main` @ `4df036c` tras el hook de arranque
  (`CLAUDE_CODE_REMOTE=true scripts/dev/cloud-session-start.sh`, que levanta PostgreSQL y las
  bases, `uv sync` y `npm ci`) `[verified-this-session]`:

  ```
  == PCRE · arranque de la sesión cloud
    ok    PostgreSQL y bases pcre, pcre_test, pcre_migcheck
    ok    uv sync (apps/backend)
    ok    npm ci (apps/frontend)
  == make verify
  All checks passed!
  147 files already formatted
  Contracts: 4 kept, 0 broken.
  274 passed in 33.50s
  migraciones nuevas probadas: 5
  toefl-ibt-2026-b1-b2: 0 errores, 23 advertencias, 7 ítems
   Test Files  6 passed (6)
        Tests  23 passed (23)
  contrato OK: OpenAPI y tipos sin diferencias
  make verify: OK
  make verify exit 0
  ```

- **E2E local:** 13/13 con Chromium y con Chrome Headless Shell (el navegador de la CI)
  `[verified-this-session]`; en la CI, job `e2e` del run anterior `[ci-run]`.

## 1. Código vs. spec (por AC)

| AC | Estado | Evidencia |
|---|---|---|
| AC-01 · `make verify` en sesión nueva tras el bootstrap | ✅ | Clon limpio + hook de arranque + `make verify` exit 0 (arriba) `[verified-this-session]`. Es la misma VM de la sesión, no una VM nueva: el clon no hereda `.venv`, `node_modules` ni archivos sin versionar. |
| AC-02 · `ci-gate` en verde en el SHA de cierre con los jobs de REQ-02 | ✅ | Run 37413020925 en `4df036c` con los 8 jobs `[ci-run]`. El run del merge de CS-12 (solo docs) se registra en `STATE.md`. |
| AC-03 · Migraciones desde vacía y desde legado + seed; `alembic check` | ✅ | Job `migrations` (`scripts/dev/migrations-check.sh`: vacía→head, legado+seed→head, `alembic check`, downgrade/upgrade de las 5 migraciones nuevas) `[ci-run]`. |
| AC-04 · Contratos de import-linter y violación provocada | ✅ | `tests/test_import_contracts.py::test_current_tree_keeps_every_contract`, `::test_violation_breaks_lint_imports`; `lint-imports` "4 kept, 0 broken" `[ci-run]`. |
| AC-05 · Invitación de un uso, vencimiento, sin rol elegible; login/logout; revocación | ✅ | `tests/identity/test_auth_api.py`: `test_invitation_is_single_use`, `test_invitation_expires`, `test_role_cannot_be_chosen`, `test_logout_revokes_the_session`, `test_reset_link_revokes_all_sessions`, `test_login_rotates_the_previous_session`; carreras en `test_races.py` `[ci-run]`. |
| AC-06 · Aislamiento con dos cuentas en cada endpoint de alumno (404) | ✅ | `tests/contract/test_isolation.py::test_each_account_only_sees_its_own_data` (lista explícita de endpoints) y pruebas por módulo (`test_attempts_are_isolated_between_accounts`, `test_answers_are_saved_without_feedback_and_isolated`) `[ci-run]`. |
| AC-07 · CSRF y `Origin` | ✅ | `tests/identity/test_csrf_origin.py`: `test_unsafe_method_without_or_with_wrong_token_is_403`, `test_foreign_or_missing_origin_is_403` `[ci-run]`. |
| AC-08 · DTO de alumno sin soluciones, explicaciones, variantes, pistas ni rúbricas | ✅ | `tests/contract/test_student_dto.py::test_student_dtos_have_no_forbidden_keys` recorre las respuestas de los endpoints de alumno; `test_lesson_announces_aids_without_content`; NI-01 (bloque PCRE) `[ci-run]`. |
| AC-09 · Idempotencia (misma clave, cuerpo distinto, concurrencia) | ✅ | `tests/practice/test_attempts_api.py`: `test_same_key_same_body_returns_same_result_and_one_row`, `test_same_key_different_body_is_409`; `tests/practice/test_concurrency.py::test_concurrent_same_key_creates_one_attempt` (dos hilos) `[ci-run]`. |
| AC-10 · Corrección con variantes válidas | ✅ | `tests/practice/test_grading.py`: `test_word_completion_accepts_variants`, `test_sentence_order_accepts_any_listed_order`, `test_multiple_choice_requires_the_exact_set` `[ci-run]`. |
| AC-11 · Editorial: revisión nueva, hash, bloqueos, atomicidad, historial | ✅ | `tests/content/test_importer.py::test_editing_a_file_creates_a_new_draft_version`; `tests/content/test_editorial_api.py`: `test_approval_is_bound_to_the_hash`, `test_material_finding_blocks_until_resolved`, `test_pending_audio_blocks_approval`, `test_publish_is_atomic_and_supersedes`, `test_withdraw_requires_reason_and_keeps_history`; `test_verifier_findings.py::test_publish_and_withdraw_race_never_deadlocks`; `test_withdrawn_pinned_lesson_is_released_and_history_kept` `[ci-run]`. |
| AC-12 · Repaso 1/3/7, reinicio, ayudas; intento + repaso en una transacción | ✅ | `tests/progress/test_review_rule.py` (reloj falso: `test_unaided_successes_walk_1_3_7_then_stay_at_7`, `test_failure_resets_and_aided_success_does_not_advance`, `test_early_review_does_not_advance`); `tests/practice/test_attempts_api.py::test_attempt_and_review_are_one_transaction` (falla provocada tras el insert) `[ci-run]`. |
| AC-13 · Métricas con fixture controlado | ✅ | `tests/progress/test_progress_api.py::test_metrics_match_a_controlled_fixture` (números exactos con duplicados), `::test_streak_counts_local_days_once` `[ci-run]`. |
| AC-14 · E2E del recorrido completo | ✅ | Job `e2e` `[ci-run]`. El recorrido se reparte en cuatro pruebas que comparten servidor: `e2e/test_first_lesson.py` (invitación, aceptación con consentimiento, L1 con respuesta, pista, fallo y acierto, recarga, **reinicio del servidor** y segunda cuenta sin acceso), `e2e/test_assessment.py::test_diagnostic_subset_resume_and_results` (diagnóstico), `e2e/test_reviews.py` (reloj +25 h, repasos vencidos y logout) y `e2e/test_publishing.py` (admin publica una revisión nueva; el historial queda). |
| AC-15 · Teléfono, teclado y axe | ✅ | `e2e/test_accessibility.py`: axe (WCAG 2.2 AA, sin graves ni críticas) en acceso, inicio, ruta, lección, comprobación y resultados con 1280 × 720 y 390 × 844; recorrido solo con teclado; `prefers-reduced-motion` `[ci-run]`. Teléfonos reales: H-6 (humano). |
| AC-16 · Contenido U1 y diagnóstico listos para revisión | ✅ | Lint 0 errores (23 advertencias: `pending_audio` y `source_pending`); `cobertura.md` y `docs/contenido/revision/{u1,inicial}.md` comprobados por el job `content`; todo en `ready-for-review`; `tests/content/test_review_packet.py` `[ci-run]`. |
| AC-17 · Imagen de producción con el comando de `heroku.yml` | ✅ | Job `image` (`scripts/ci/image-smoke.sh`): build, `release` y `run.web` de `heroku.yml`; `/health` 200, `/api/v1/ready` 200, `/` con la SPA, `/api/v1/no-existe` 404 JSON, asset inexistente 404 `[ci-run]`. |
| AC-18 · Bundle sin llaves ni hosts de proveedores | ✅ | Job `image`, paso "grep del bundle" (`scripts/ci/bundle-grep.sh`) `[ci-run]`. |
| AC-19 · Cabeceras, cookie y Markdown | ✅ | `tests/test_security_headers.py`, `tests/identity/test_auth_api.py::test_login_sets_secure_host_cookie`, `apps/frontend/src/components/Markdown.test.tsx`; tabla de controles en `docs/reviews/mvp-01-seguridad.md` `[ci-run]`. |
| AC-20 · Smoke de rendimiento registrado | ✅ | Sección 5 y `docs/reviews/mvp-01-perf-smoke.md`: todos los p95 < 800 ms, 0 errores `[verified-this-session]`. Sin desviación. |
| AC-21 · `deploy.yml` con actionlint; run omitido tras el merge | ✅ (parte de G1 ⏸) | actionlint en el job `workflows` `[ci-run]`; run [37412451354](https://github.com/astraDukoWave/pcre-learning-platform/actions/runs/37412451354) `skipped` en `33b14f1` y [37413167955](https://github.com/astraDukoWave/pcre-learning-platform/actions/runs/37413167955) `skipped` en `4df036c` `[verified-this-session]`. "Deploy no configurado" se comprueba en G1 (el spec lo asigna ahí; runbook §2.3). |
| AC-22 · Exportación y borrado | ✅ | `tests/identity/test_export_delete.py`: `test_export_contains_only_own_data_without_secrets`, `test_delete_requires_the_password`, `test_delete_removes_every_row_and_allows_reinvite`; `tests/identity/test_data_registry.py` (toda tabla con datos del usuario registrada y toda FK a `users` en cascada) `[ci-run]`. |
| AC-23 · Panel del piloto con internas excluidas | ✅ | `tests/insights/test_insights.py::test_pilot_panel_excludes_internal_accounts` (números exactos) `[ci-run]`. |
| AC-24 · Docs al día | ✅ | `HANDOFF.md`, `STATE.md`, `docs/runbook.md`, este reporte y `docs/reviews/mvp-01-activacion-cto-review.md` en el PR de CS-12 `[verified-this-session]`. |

## 2. Tests automatizados

- Backend: 274 pruebas contra PostgreSQL 16 real, sin red (`pytest-socket`); ruff, mypy
  estricto e import-linter (4 contratos) `[ci-run]`.
- Frontend: 23 pruebas de Vitest, `tsc -b`, ESLint sin advertencias y build `[ci-run]`.
- Contrato API: `docs/api/openapi.json` y `schema.d.ts` sin diferencias `[ci-run]`.
- Migraciones: 5 nuevas (`identity_v1`, `content_v1`, `practice_v1`, `assessment_v1`,
  `insights_v1`), todas *expand* `[ci-run]`.
- E2E: 13 pruebas (primer tramo, formatos, comprobaciones, repasos, publicación y
  accesibilidad) `[ci-run]`.

## 3. Contratos y casos edge

| Caso | Cobertura |
|---|---|
| EDGE-01 invitación vencida o usada | `test_invitation_expires`, `test_invitation_is_single_use`; mensaje en `auth.test.tsx` ("explains an expired invitation") |
| EDGE-02 doble envío | Idempotencia (AC-09); `client.test.ts` ("reports network failures without pretending success") |
| EDGE-03 sesión vencida a mitad de lección | Borrador local en `features/lesson/drafts.ts`; **sin prueba automatizada** (observación) |
| EDGE-04 revisión nueva a mitad de lección | `test_publish_is_atomic_and_supersedes`, `e2e/test_publishing.py` |
| EDGE-05 revisión retirada a mitad de lección | `test_withdrawn_pinned_lesson_is_released_and_history_kept` |
| EDGE-06 recurso ajeno | AC-06 |
| EDGE-07 audio que no carga | Comprobación: `test_submit_grades_by_objective_and_is_idempotent` y `e2e/test_assessment.py` (ítem "no evaluable (audio)"). Práctica: botón "Reintentar el audio" y transcripción tras dos fallas en `AudioPlayer.tsx`, **sin prueba automatizada de la falla** (observación) |
| EDGE-08 micrófono denegado | `e2e/test_formats.py::test_speaking_records_locally_and_handles_a_denied_microphone` |
| EDGE-09 diagnóstico repetido | `test_diagnostic_runs_once_until_an_admin_resets_it`, `test_checkpoint_repeats_with_numbered_runs` |
| EDGE-10 cambio de zona horaria | `local_day` se fija al enviar (`test_request_hash_and_local_day`); **sin prueba del cambio** (observación) |
| EDGE-11 contenido inválido | Lint en la CI (`test_lint.py`), `test_invalid_content_writes_nothing`; la release phase de Heroku se observa en G1 |
| EDGE-12 reinicio durante una petición | Reintento con la misma `Idempotency-Key` (`client.test.ts`); reinicio en `e2e/test_first_lesson.py` |
| EDGE-13 aprobar o publicar con bloqueos | `test_material_finding_blocks_until_resolved`, `test_pending_audio_blocks_approval`, `test_approval_is_bound_to_the_hash` |
| EDGE-14 cuenta borrada | `test_delete_removes_every_row_and_allows_reinvite` |
| EDGE-15 cuenta interna | `test_pilot_panel_excludes_internal_accounts` |
| EDGE-16 demasiados logins | `test_login_rate_limit`, `test_rate_limit_uses_the_last_forwarded_ip` |
| EDGE-17 atrás durante una comprobación | `test_answers_are_saved_without_feedback_and_isolated`; `e2e/test_assessment.py` (retoma) |

## 4. QA de producto / E2E

- Automatizado: sección 2 y AC-14/AC-15 `[ci-run]`.
- **Pendiente humano** (no bloquea el cierre del ciclo; son pasos de los gates):
  - H-6: iPhone (Safari) y Android (Chrome) reales, runbook §12 (antes de G4).
  - Escuchar los MP3 de U1 y del diagnóstico (G2).
  - Revisión editorial de U1 y del diagnóstico con los paquetes de revisión (G3).

## 5. Smoke de deployment y rendimiento

- Imagen de producción: AC-17 `[ci-run]`. Heroku todavía no existe: el smoke de
  `deploy.yml` (`/health`, `/api/v1/ready` con el head esperado y `/`) corre en G1.
- Rendimiento (AC-20, NFR-03), build de producción local, 100 peticiones por endpoint, 10
  concurrentes `[verified-this-session]`:

  | Endpoint | p50 (ms) | p95 (ms) | Máx. (ms) | Errores |
  |---|---:|---:|---:|---:|
  | `GET /me` | 57.3 | 87.2 | 94.7 | 0 |
  | `GET /learning-paths/{id}` | 158.4 | 230.4 | 245.9 | 0 |
  | `GET /lessons/{id}` | 98.8 | 113.5 | 161.4 | 0 |
  | `POST /attempts` | 154.4 | 229.2 | 280.7 | 0 |
  | `GET /me/progress` | 301.3 | 410.9 | 452.7 | 0 |

## 6. Proceso

- 12 change sets, un PR por change set (#3 a #13 y el de CS-12), todos con merge commit y
  `ci-gate` en verde en el SHA del head antes del merge (delegación de G0, ruleset activo).
- Verificadores independientes: CS-03 y CS-04 (hallazgos corregidos antes del merge; ver
  `STATE.md`) y este cierre.
- Notas de interpretación sin cambio de alcance: NI-01 a NI-04 (`STATE.md`). Desviaciones:
  ninguna.
- H-1b (`ci-gate` como check requerido) sigue pendiente: el ruleset tiene `deletion`,
  `non_fast_forward` y `pull_request` `[verified-this-session]`. El dictamen de activación lo
  pide antes de G1.

### Verificador independiente (cierre)

Se completa con su resultado antes del merge.

## Regresiones

Ninguna conocida: la suite completa pasa en cada PR y en `main`.

## Deuda introducida

- EDGE-03, EDGE-10 y la falla de audio en práctica (EDGE-07) sin prueba automatizada
  (comportamiento implementado).
- `/api/v1/ready` responde 503 tras un rollback de código que cruce una migración
  (documentado en el runbook §6).
- La CLI de Heroku se instala en `deploy.yml` con `npm install --global heroku@10`; la
  versión mayor se actualiza a mano.
- Fuentes de Cambridge y del Consejo de Europa `pending` (la sesión no llega a esos hosts);
  se confirman en G3.

## Decisión

**✅ listo**, con los pasos humanos de los gates G1–G4 (`docs/reviews/mvp-01-activacion-cto-review.md`)
y H-1b.
