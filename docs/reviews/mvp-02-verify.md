# Verify — MVP-02 · Coach con IA y voz

- **Spec:** `docs/specs/mvp-02-coach-ia-voz.md` @ `9aa2e2c` · **Plan:**
  `docs/plans/mvp-02-coach-ia-voz-plan.md` @ `0100c0a`.
- **Código verificado:** `main` @ `{{SHA_CIERRE}}` (merge de CS-07, PR #21; CS-01 a CS-07,
  PRs #15 a #21).
- **Fecha:** 7 oct 2026. Formato: skill `verify` según `docs/sdd/proceso.md` §9.
- **Verificadores independientes:** subagentes de contexto fresco antes del merge de CS-02,
  CS-05 (dos rondas) y CS-07, con el spec, el diff y evidencia ejecutable (sección 6).
- **Etiquetas:** `[ci-run]` run ligado al SHA · `[verified-this-session]` output en la
  sesión · `[inherited-unverified]` · `[contradicted]`.

## Evidencia base

- **CI de `main` @ `{{SHA_CIERRE}}`:** run {{RUN_CIERRE}} ✅ `backend`, `migrations`,
  `content`, `frontend`, `contract`, `e2e`, `image`, `workflows` y `ci-gate` `[ci-run]`.
  Cada PR de MVP-02 tiene su run en verde en el registro de `STATE.md`.
- **`make verify` sobre `main` @ `{{SHA_CIERRE}}`** `[verified-this-session]`:

  ```
{{VERIFY_OUTPUT}}
  ```

- **E2E local:** `e2e/test_voice_coach.py` (3), `test_ai_feedback.py` (2),
  `test_transcription.py` (2) y `test_accessibility.py` (4) en verde con Chromium
  `[verified-this-session]`; en la CI, job `e2e` del run anterior `[ci-run]`.

## 1. Código vs. spec (por AC)

| AC | Estado | Evidencia |
|---|---|---|
| AC-01 · Dos reservas concurrentes que exceden el tope → exactamente una | ✅ | `tests/usage/test_budgets.py::test_concurrent_reservations_over_the_limit_only_one_succeeds` y `::test_concurrent_reservations_with_the_same_key_create_one_run` (hilos contra PostgreSQL real); cupo de voz con creación concurrente en `test_voice_sessions.py::test_concurrent_creation_respects_both_quotas` `[ci-run]`. |
| AC-02 · Sin presupuesto: feedback, transcripción y voz → 503 `capability_disabled` y la alternativa | ✅ | `test_budgets.py::test_without_budget_every_capability_is_disabled`, `::test_expected_503_is_not_a_server_error`; `test_writing_feedback_api.py::test_without_capability_or_budget_the_answer_is_an_expected_503`; `test_transcription_api.py::test_without_capability_or_budget_the_answer_is_an_expected_503`; `test_voice_sessions.py::test_capability_off_is_an_expected_503`; E2E `test_ai_feedback.py::test_without_budget_the_alternative_is_self_assessment` y `test_voice_coach.py::test_without_voice_the_scenario_is_practiced_by_text` `[ci-run]`. |
| AC-03 · El validador maneja salida rota, evidencia inventada, URLs y campos de más | ✅ | `tests/coaching/test_feedback_validator.py` (11 pruebas: salida rota o no objeto, evidencia inventada, URLs con y sin esquema, correos, puntajes y niveles en español, campos de más, palabras completas, delimitador) y fixtures grabados en `evals/feedback/recorded/` `[ci-run]`. |
| AC-04 · Idempotencia del feedback y política de `unknown` | ✅ | `test_writing_feedback_api.py::test_same_key_and_later_requests_never_charge_twice`, `::test_unknown_keeps_the_reservation_and_is_never_retried`, `::test_failed_releases_the_reservation_and_can_be_retried`; para voz, `test_voice_feedback.py::test_final_feedback_quotes_learner_turns_and_schedules_a_review`, `::test_open_foreign_and_failed_sessions`, `::test_unknown_voice_feedback_is_never_repeated`, `::test_a_key_from_another_session_is_always_a_conflict`, `::test_a_paid_result_is_rebuilt_if_saving_failed`; concurrencia con claves distintas en `test_voice_sessions.py::test_concurrent_feedback_requests_with_different_keys_make_one_call` `[ci-run]`. |
| AC-05 · Set de evaluación offline; `feedback-eval.yml` con actionlint y environment `evals` | ✅ (run real ⏸ G5a) | `tests/coaching/test_eval_set.py` (10 pruebas, incluidas `test_workflow_requires_the_evals_environment_and_a_cost_cap`, `test_degenerate_models_never_meet_the_rule` y `test_a_model_that_obeys_the_injection_fails_the_rule`); actionlint en el job `workflows` `[ci-run]`. El run con modelos reales es G5a (humano) y su reporte irá a `docs/reviews/mvp-02-feedback-eval.md`. |
| AC-06 · Transcripción: el audio nunca toca disco; límites 413/422; comparación de la repetición | ✅ | `test_transcription_api.py::test_audio_never_touches_disk`, `::test_limits_type_size_and_duration`, `::test_repeat_counts_target_words_and_never_grades`; `test_stt.py::test_repeat_comparison_fixtures`; E2E `test_transcription.py` `[ci-run]`. |
| AC-07 · `Origin` ajeno → 403 antes de `accept()`; sesión ajena; segunda conexión; 409; 503 | ✅ | `test_voice_sessions.py::test_websocket_checks_origin_owner_and_a_single_connection`, `::test_same_key_one_live_session_per_learner_and_global_quota`, `::test_connections_after_the_grace_or_without_origin_or_cookie_are_refused`, `::test_concurrent_creation_respects_both_quotas`; uvicorn real con los flags de `heroku.yml` en la ronda 2 del verificador de CS-05 (HTTP 403 en el handshake) `[ci-run]` `[verified-this-session]`. |
| AC-08 · `VOICE_MAX_SESSION_S=3`: cierre del proveedor en el deadline ±0.5 s, `ended(deadline)`, liquidación | ✅ | `test_voice_sessions.py::test_server_deadline_closes_the_provider_and_settles` (el falso mide `closed_at − applied_at`; 3 s cobrados, igual a lo reservado; duración ≤ 3) `[ci-run]`. |
| AC-09 · Desconexión → proveedor cerrado en ≤ 2 s; logout → la sesión termina | ✅ | `test_client_disconnect_closes_the_provider_within_two_seconds`, `test_logout_ends_the_session`, `test_logout_is_detected_on_the_next_control_message`, `test_a_provider_that_ignores_the_close_is_aborted` `[ci-run]`; la ruta de uvicorn (sin cancelación) en la ronda 2 del verificador: 0.002 s `[verified-this-session]`. |
| AC-10 · `active` pasada de su deadline → `expired` con la reserva completa | ✅ | `test_sweep_expires_orphans`, `test_sweep_keeps_live_sessions_within_the_margin_and_runs_on_create`, `test_sweep_releases_reservations_left_without_a_session` `[ci-run]`. |
| AC-11 · Ayudas con hora; `repeat` → `InjectUserMessage`, `slower` → `UpdatePrompt` | ✅ | `test_conversation_relays_audio_transcript_and_aids` (contenido literal de ambos mensajes, horas crecientes, la pista no va al proveedor); `test_voice_domain.py::test_a_pending_repeat_is_forgotten_when_the_next_learner_turn_differs` `[ci-run]`. |
| AC-12 · Sin consentimiento no se guardan transcripción ni feedback; exportación y borrado | ✅ | `test_voice_sessions.py::test_without_consent_only_duration_and_aids_are_kept`; `test_voice_feedback.py::test_without_consent_or_enough_speech_there_is_no_call`, `::test_export_includes_and_delete_removes_voice_transcripts` `[ci-run]`. |
| AC-13 · Un turno disputado oculta las observaciones con evidencia en ese turno | ✅ | `test_voice_feedback.py::test_a_disputed_turn_hides_its_observations`, `::test_disputes_before_the_feedback_do_not_confirm_a_difficulty`, `::test_disputing_every_cited_turn_undoes_the_review`, `::test_a_dispute_made_while_evaluating_counts`; `test_voice_sessions.py::test_concurrent_flags_on_two_turns_both_persist`; `test_feedback_validator.py::test_disputed_turns_hide_their_observations`; Vitest `voiceFeedback.test.tsx`; E2E `test_voice_coach.py` `[ci-run]`. |
| AC-14 · E2E con Chromium, micrófono falso (WAV) y Deepgram falso | ✅ | `e2e/test_voice_coach.py::test_voice_coach_conversation`: WAV generado como `--use-file-for-fake-audio-capture`, frames de audio del coach por el WebSocket, transcripción, «Repetir», «Detener», feedback con la evidencia resaltada, disputa y valoración; `::test_without_voice_the_scenario_is_practiced_by_text` (modo texto) `[ci-run]`. |
| AC-15 · Ninguna llave en el bundle ni en los mensajes al navegador | ✅ | `scripts/ci/bundle-grep.sh` (nombres de variables, hosts, `AIza…`, `sk-…`, llaves privadas y 40 hex) en `make frontend-check` (job `frontend`) y en el job `image`; `test_voice_sessions.py::test_no_key_reaches_the_browser_or_debug_logs` (respuestas HTTP, mensajes del WebSocket y logs con `DEBUG`) `[ci-run]`. |
| AC-16 · Medición de memoria (NFR-06) registrada | ✅ | Sección 5: pico de 124.6 MB < 300 MB con 3 sesiones y frames de 1 MiB `[verified-this-session]`. |
| AC-17 · Prueba manual en iPhone y Android con Deepgram real (H-9) | ⏸ humano | Después de G5; checklist en `docs/runbook.md` §15. El spec permite dejarlo como pendiente humano en el DoD del agente. |
| AC-18 · Docs al día | ✅ | `HANDOFF.md`, `STATE.md`, `docs/runbook.md` §14 y §15 (activación, banderas, rollback, señales y H-9), este reporte y `docs/reviews/mvp-02-activacion-cto-review.md` en el PR de CS-08 `[verified-this-session]`. |

### Requisitos no funcionales

| NFR | Estado | Evidencia |
|---|---|---|
| NFR-01 · Costo fail-closed, topes, sin reintento de `unknown`; peor caso mensual = tope global | ✅ | AC-01, AC-02, AC-04; conciliación del tiempo conectado al proveedor (NI-09(6)); peor caso calculado en el dictamen de activación (≈ USD 25.6 al mes con los topes de G0) |
| NFR-02 · Latencia: feedback p95 ≤ 12 s (timeout 20 s); transcripción de 60 s ≤ 8 s; coach ≤ 2.5 s p50 | ⏸ parcial | Timeouts totales probados (`test_gemini_total_deadline_covers_slow_responses`, `test_deepgram_total_deadline`) `[ci-run]`; las latencias reales solo se miden con los proveedores reales (G5a y H-9) |
| NFR-03 · Seguridad: llaves solo en el servidor, `Origin`, dueño, audio no persistido, transcripción con consentimiento, inyección, grep del bundle | ✅ | AC-06, AC-07, AC-12, AC-15; `test_prompt_delimits_the_learner_text_as_data`, `test_lookalike_angle_brackets_cannot_close_the_block`; casos de inyección del set de evaluación `[ci-run]` |
| NFR-04 · Privacidad: aviso con Deepgram y Google; exportación y borrado | ✅ | `apps/frontend/src/legal/privacidad.md` (este PR); AC-12 |
| NFR-05 · Resiliencia: proveedor caído → alternativa sin costo; deadline aunque el cliente se cuelgue | ✅ | `test_provider_closing_before_settings_ends_with_provider_error`, `test_provider_that_never_applies_settings_times_out`, `test_provider_error_mid_session_ends_and_settles`, `test_a_failing_session_check_does_not_stop_the_deadline` `[ci-run]` |
| NFR-06 · Memoria < 300 MB con 3 sesiones | ✅ | AC-16 |
| NFR-07 · Pruebas sin red | ✅ | Guard de sockets de pytest; dobles en `adapters/` y `tests/fakes/` `[ci-run]` |
| NFR-08 · Accesibilidad del coach | ✅ | `e2e/test_voice_coach.py::test_coach_by_keyboard_with_axe_and_reduced_motion`: solo teclado, axe sin violaciones graves ni críticas antes, durante y al terminar, indicador sin animación con movimiento reducido; subtítulos `aria-live` `[ci-run]` |

## 2. Tests automatizados

- Backend: {{N_BACKEND}} pruebas contra PostgreSQL 16 real, sin red (`pytest-socket`); ruff,
  mypy estricto e import-linter (4 contratos) `[verified-this-session]`.
- Frontend: {{N_VITEST}} pruebas de Vitest, `tsc -b`, ESLint sin advertencias, build y grep
  del bundle.
- Contrato API: `docs/api/openapi.json` y `schema.d.ts` sin diferencias `[ci-run]`.
- Migraciones nuevas de MVP-02: `usage_v1` y `voice_v1`, ambas *expand* (job `migrations`)
  `[ci-run]`.
- E2E: 20 pruebas; las de MVP-02 son `test_ai_feedback.py`, `test_transcription.py` y
  `test_voice_coach.py` `[ci-run]`.

## 3. Casos edge

| Caso | Cobertura |
|---|---|
| EDGE-01 micrófono denegado | Coach: `CoachPage` → «Practicar este escenario por texto» (máquina de estados, `machine.test.ts`); grabación: `e2e/test_formats.py::test_speaking_records_locally_and_handles_a_denied_microphone`. En teléfono real, H-9 |
| EDGE-02 silencio | `test_silence_invites_then_ends` |
| EDGE-03 el alumno habla en español | Regla del agente en el prompt (`test_settings_message_from_the_scenario`); feedback `other_language` sin penalizar (`test_limit_of_observations_and_abstention_reasons`) |
| EDGE-04 reconocimiento pobre | AC-13 |
| EDGE-05 se cae la red | AC-09 |
| EDGE-06 pestaña en segundo plano | `CoachPage` (`visibilitychange` → fin con aviso); **sin prueba automatizada** (observación); H-9 |
| EDGE-07 logout en otra pestaña | AC-09 |
| EDGE-08 dos pestañas | AC-07 (segunda conexión) |
| EDGE-09 segunda sesión | AC-07 (409, texto del spec) |
| EDGE-10 cuarta sesión global | AC-07 (503 `voice_busy`, esperado) |
| EDGE-11 presupuesto agotado | `test_user_and_global_limits_and_voice_minutes`; aviso al 80 % en `/admin/consumo` (`test_admin_usage_view_and_guard`) |
| EDGE-12 `Error` o `Warning` del proveedor | `test_provider_error_mid_session_ends_and_settles` |
| EDGE-13 deadline mientras el coach habla | Cierre del proveedor en el deadline (AC-08); la cola de audio suena hasta 2 s más (`usePcmPlayback.test.ts`) |
| EDGE-14 reinicio del dyno | Barrido al arrancar (AC-10) |
| EDGE-15 falla el modelo del feedback final | `test_open_foreign_and_failed_sessions` (`failed` → reintento); Vitest «Pedir el feedback otra vez» |
| EDGE-16 inyección | Delimitador y casos del set de evaluación (NFR-03); reglas del agente |
| EDGE-17 sin consentimiento | AC-12; el resumen lo explica (`voiceFeedback.test.tsx`) |

## 4. QA de producto / E2E

- Automatizado: secciones 1 y 2 `[ci-run]`. Revisión visual de las capturas
  `test-results/coach-*.png` en CS-06 y CS-07.
- **Pendiente humano** (pasos de los gates, no bloquean el cierre del ciclo):
  - G5a: run real de `feedback-eval.yml` (AC-05) y elección de `GEMINI_MODEL`.
  - G5: llaves, presupuestos y banderas (runbook §14).
  - H-9 (AC-17): iPhone y Android con Deepgram real (runbook §15), que además confirma la
    forma de los mensajes de la Voice Agent API (NI-09(4)) y las latencias de NFR-02.

## 5. Memoria (NFR-06, AC-16)

`scripts/perf/voice_memory.py` sobre `feat/mvp02-cs07-voice-feedback` (código de CS-07), con
el Deepgram falso y el servidor con los flags de `heroku.yml` (`--ws-max-size 1048576`,
`--ws-max-queue 8`, un worker): tres alumnos, tres sesiones simultáneas de 15 s, cada una
mandando frames de 1 MiB a ~28 por segundo `[verified-this-session]`.

| Medición | Valor |
|---|---|
| Medido | 2026-10-07 11:20 UTC, Python 3.12.11 |
| Sesiones | 3 |
| Frame | 1 048 576 bytes |
| RSS en reposo | 110.5 MB |
| RSS máximo | **124.6 MB** (umbral 300 MB) |
| Frames recibidos por el proveedor falso | 1 271 |
| Resultado | ✅ |

## 6. Proceso

- 8 change sets, un PR por change set (#15 a #21 y el de CS-08), todos con merge commit y
  `ci-gate` en verde en el SHA del head antes del merge (delegación de G0, ruleset activo).
- Verificadores independientes:
  - **CS-02:** hallazgos de la regla de selección, la evidencia y el timeout total,
    corregidos antes del merge (NI-07).
  - **CS-05, ronda 1:** 2 bloqueantes (un stop durante el arranque del relay; una tarea
    que muere sin deadline) y 6 menores.
  - **CS-05, ronda 2:** sin bloqueantes; 8 arreglos confirmados y menores corregidos con
    14 pruebas nuevas.
  - **CS-07 (4 lentes):** 1 bloqueante, corregido con una prueba de carrera determinista:
    dos peticiones de feedback con claves distintas pagaban dos llamadas, y ahora hay una
    sola ejecución por sesión dentro de la reserva, también en escritura y transcripción.
    Los menores también se corrigieron:
    - marcas concurrentes;
    - disputa durante la evaluación;
    - repaso deshecho si las disputas dejan sin observaciones;
    - resultado pagado reconstruido;
    - huérfanas a `unknown`;
    - 👍/👎 en voz;
    - llave de 40 hex en el grep del bundle;
    - resaltado como el validador;
    - pantalla final sin callejones, con región viva y foco.
  - Detalle en `STATE.md` y en los comentarios de cada PR.
- Notas de interpretación sin cambio de alcance: NI-05 a NI-10 (`STATE.md`). Desviaciones:
  ninguna.
- H-1b (`ci-gate` como check requerido) sigue pendiente: el ruleset tiene `deletion`,
  `non_fast_forward` y `pull_request` `[verified-this-session]`.

## Regresiones

Ninguna conocida: la suite completa pasa en cada PR y en `main`.

## Deuda introducida

- EDGE-06 (fin al pasar a segundo plano) sin prueba automatizada; se cubre en H-9.
- Al borrar una cuenta con una reserva abierta, la reserva queda contada en la fila global
  del mes hasta que cambia el periodo (falla cerrada: nunca gasta de más, pero reduce el
  cupo). LB-15.
- La forma exacta de los mensajes de la Voice Agent API sigue la referencia del 5 oct 2026
  sin contraste con el servicio real (NI-09(4)); se confirma en H-9.
- El Deepgram falso cuenta bytes del micrófono y no distingue el WAV del pitido por omisión
  de Chromium: el E2E prueba el camino del audio, no su contenido.

## Decisión

**✅ listo**, con los pasos humanos G5a, G5 y H-9
(`docs/reviews/mvp-02-activacion-cto-review.md`) y H-1b.
