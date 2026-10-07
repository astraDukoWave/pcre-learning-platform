# STATE.md — ciclo activo

**Fase:** MVP-01 cerrado el 6 oct 2026 (`docs/reviews/mvp-01-verify.md` ✅ y dictamen de
activación G1–G4); MVP-02 en ejecución en la misma sesión cloud con `/goal`.
G0 aprobado por Jonathan el 5 oct 2026 (PR #2).
**Change set en curso:** ver la última línea del registro
(`docs/plans/mvp-02-coach-ia-voz-plan.md` desde MVP-02 CS-01).
**Encadenamiento** (decisión 2 = A): un `/goal` para MVP-01 y después
MVP-02; MVP-03 espera a G6.

## Gates

| Gate | Qué autoriza | Estado |
|---|---|---|
| G0 | Paquete MVP-01/02/03; arranque autónomo; delegación de merges | **aprobado** el 5 oct 2026 |
| G1 | Deploy a Heroku | no iniciado |
| G2 | Audio TTS por unidad | no iniciado |
| G3 | Publicación de contenido por unidad | no iniciado |
| G4 | Alumnos reales | no iniciado |
| G5 / G5a | IA y voz / benchmark del feedback | no iniciado |
| G6 | Arranque de MVP-03 | no iniciado |

## Decisiones de G0 (firmadas por Jonathan el 5 oct 2026)

1. **Delegación de merges: sí**, solo para MVP-01 y MVP-02. Claude mergea
   con merge commit cuando `ci-gate` está en verde en el SHA del head, el
   ruleset de `main` está activo y ninguna desviación `pending-human` afecta
   al change set. Deploys, secretos, publicación de contenido e
   invitaciones siguen siendo de Jonathan.
2. **Encadenamiento: A.**
3. **Techo de gasto del piloto** (se aplica en G5):
   - USD 25 al mes global → `BUDGET_GLOBAL_MONTHLY_MICROUSD=25000000`.
   - USD 8 al mes por alumno → `BUDGET_USER_MONTHLY_MICROUSD=8000000`.
   - 60 minutos de voz por alumno al mes →
     `VOICE_MAX_MINUTES_PER_USER_MONTH=60`.
   - Dyno **Basic** en G1.

Ratificados en G0: ADR-08 (tablas nuevas para el currículo) y la división
en tres ciclos. Los ajustes del plan que no cambien alcance ni contrato se
anotan en el registro; cualquier otra desviación queda `pending-human`.

## Repo y entorno

- Ruleset `main` (id 24546040) activo: `deletion`, `non_fast_forward` y
  `pull_request` con 0 aprobaciones `[verified-this-session: API REST, 5 oct
  2026]`. Pendiente **H-1b**: `ci-gate` como check requerido, después del
  primer run de CI de CS-01.
- Comprobado al cerrar MVP-01 (6 oct 2026): ruleset 24546040 `active` con `deletion`,
  `non_fast_forward` y `pull_request`; **sin** `required_status_checks` (H-1b sigue
  pendiente) `[verified-this-session: API REST]`.
- Comprobado al arrancar MVP-01 (6 oct 2026): `origin/main` @ `a642934`, 0 PRs
  abiertos, ruleset con `deletion`, `non_fast_forward` y `pull_request`
  `[verified-this-session: API REST]`.
- Environment cloud: `CLAUDE_CODE_REMOTE=true`, PostgreSQL 16, Node 22, uv y
  Docker presentes; PyPI, npm y GitHub alcanzables `[verified-this-session]`.
  Red Trusted y ausencia de llaves `[inherited-unverified]` (ninguna variable de
  proveedor en el entorno).

## Registro de change sets

| Ciclo | CS | Rama | PR | SHA mergeado | Run de CI | Evidencia | Fecha |
|---|---|---|---|---|---|---|---|
| — | paquete G0 | `docs/sdd-mvp-specs` | [#2](https://github.com/astraDukoWave/pcre-learning-platform/pull/2) | `a642934` | sin CI (la crea CS-01) | aprobación de Jonathan (G0) | 5 oct 2026 |
| MVP-01 | CS-01 · base y CI | `ci/mvp01-cs01-base` | [#3](https://github.com/astraDukoWave/pcre-learning-platform/pull/3) | `1e47bdb` (head `c078788`) | [37393819247](https://github.com/astraDukoWave/pcre-learning-platform/actions/runs/37393819247) ✅ backend, migrations, workflows, ci-gate | `make verify` exit 0 `[verified-this-session]` · CI `[ci-run]` | 6 oct 2026 |
| MVP-01 | CS-02 · frontend e imagen | `feat/mvp01-cs02-frontend-image` | [#4](https://github.com/astraDukoWave/pcre-learning-platform/pull/4) | `c61fa9b` (head `e518a4e`) | [37394717138](https://github.com/astraDukoWave/pcre-learning-platform/actions/runs/37394717138) ✅ 7 jobs + ci-gate | `make verify` exit 0; imagen con sondas AC-17 y grep AC-18 en el job `image` `[ci-run]` | 6 oct 2026 |
| MVP-01 | CS-03 · identidad | `feat/mvp01-cs03-identity` | [#5](https://github.com/astraDukoWave/pcre-learning-platform/pull/5) | `e0ce77b` (head `fcff1d2`) | [37396602133](https://github.com/astraDukoWave/pcre-learning-platform/actions/runs/37396602133) ✅ 7 jobs + ci-gate | `make verify` exit 0 (137 pruebas); [verificador independiente](https://github.com/astraDukoWave/pcre-learning-platform/pull/5#issuecomment-6006957824): 0 bloqueantes, 5 menores corregidos en `fcff1d2` | 6 oct 2026 |
| MVP-01 | CS-04 · contenido y editorial | `feat/mvp01-cs04-content` | [#6](https://github.com/astraDukoWave/pcre-learning-platform/pull/6) | `fd27fe1` (head `cb88907`) | [37399146747](https://github.com/astraDukoWave/pcre-learning-platform/actions/runs/37399146747) ✅ 8 jobs + ci-gate | `make verify` exit 0 (195 pruebas); [verificador independiente](https://github.com/astraDukoWave/pcre-learning-platform/pull/6#issuecomment-6007370846): 1 bloqueante y 8 menores corregidos en `cb88907`; NI-01 | 6 oct 2026 |
| MVP-01 | CS-05 · primera lección E2E | `feat/mvp01-cs05-first-lesson` | [#7](https://github.com/astraDukoWave/pcre-learning-platform/pull/7) | `e45ede1` (head `5502eb4`) | [37399904620](https://github.com/astraDukoWave/pcre-learning-platform/actions/runs/37399904620) ✅ 8 jobs + ci-gate | `make verify` exit 0 (236 pruebas); E2E local 3/3 y en la CI | 6 oct 2026 |
| MVP-01 | CS-06 · formatos, audio y escenario | `feat/mvp01-cs06-formats-audio` | [#8](https://github.com/astraDukoWave/pcre-learning-platform/pull/8) | `1a592d4` (head `f2ed3da`) | [37402697350](https://github.com/astraDukoWave/pcre-learning-platform/actions/runs/37402697350) ✅ 8 jobs + ci-gate (el primer run, [37402283679](https://github.com/astraDukoWave/pcre-learning-platform/actions/runs/37402283679), falló: empate de reloj falso en una prueba y micrófono en Chrome Headless Shell; corregidos en `f2ed3da`) | `make verify` exit 0 (249 pruebas backend, 21 Vitest); E2E 5/5 local (Chromium y headless shell) y en la CI; `generate_audio.py --dry-run` U1: 9 guiones, 1 091 caracteres, USD 0.0327; NI-02 | 6 oct 2026 |
| MVP-01 | CS-07 · comprobaciones | `feat/mvp01-cs07-assessments` | [#9](https://github.com/astraDukoWave/pcre-learning-platform/pull/9) | `ede8ea6` (head `455f45d`) | [37403902453](https://github.com/astraDukoWave/pcre-learning-platform/actions/runs/37403902453) ✅ 8 jobs + ci-gate | `make verify` exit 0 (257 pruebas backend, 22 Vitest, migraciones nuevas probadas: 4); E2E 7/7 local (Chromium y headless shell) y en la CI; NI-03 | 6 oct 2026 |
| MVP-01 | CS-08 · progreso, repasos e inicio | `feat/mvp01-cs08-progress` | [#10](https://github.com/astraDukoWave/pcre-learning-platform/pull/10) | `7c0f8c0` (head `80078f0`) | [37404920643](https://github.com/astraDukoWave/pcre-learning-platform/actions/runs/37404920643) ✅ 8 jobs + ci-gate | `make verify` exit 0 (261 pruebas backend, 22 Vitest); AC-13 con números exactos; E2E 8/8 local (Chromium y headless shell) y en la CI | 6 oct 2026 |
| MVP-01 | CS-09 · panel editorial y piloto | `feat/mvp01-cs09-editorial-pilot` | [#11](https://github.com/astraDukoWave/pcre-learning-platform/pull/11) | `9709535` (head `4976623`) | [37410741432](https://github.com/astraDukoWave/pcre-learning-platform/actions/runs/37410741432) ✅ 8 jobs + ci-gate (el run [37410254736](https://github.com/astraDukoWave/pcre-learning-platform/actions/runs/37410254736) falló en `e2e`: un guardado lento movía de pregunta en la corrida; corregido en `4976623` con una prueba que retiene el guardado) | `make verify` exit 0 (268 pruebas backend, 22 Vitest, migraciones nuevas probadas: 5); AC-23 con fixture (internas excluidas); E2E 9/9 local y en la CI | 6 oct 2026 |
| MVP-01 | CS-10 · seguridad, legales, accesibilidad, rendimiento y deploy | `feat/mvp01-cs10-hardening-deploy` | [#12](https://github.com/astraDukoWave/pcre-learning-platform/pull/12) | `33b14f1` (head `cd07d64`) | [37412078255](https://github.com/astraDukoWave/pcre-learning-platform/actions/runs/37412078255) ✅ 8 jobs + ci-gate | `make verify` exit 0 (271 pruebas backend, 23 Vitest); axe sin violaciones graves en las seis pantallas (escritorio y 390 × 844), recorrido con teclado y movimiento reducido; E2E 13/13 local y en la CI; smoke de rendimiento: todo p95 < 800 ms (`docs/reviews/mvp-01-perf-smoke.md`); `deploy.yml` con actionlint; AC-21: run de `deploy.yml` tras el merge **skipped** ([37412451354](https://github.com/astraDukoWave/pcre-learning-platform/actions/runs/37412451354)), CI de `main` ✅ ([37412274783](https://github.com/astraDukoWave/pcre-learning-platform/actions/runs/37412274783)); NI-04 | 6 oct 2026 |
| MVP-01 | CS-11 · contenido U1 listo para revisión | `feat/mvp01-cs11-u1-ready` | [#13](https://github.com/astraDukoWave/pcre-learning-platform/pull/13) | `4df036c` (head `536e301`) | [37412837444](https://github.com/astraDukoWave/pcre-learning-platform/actions/runs/37412837444) ✅ 8 jobs + ci-gate; `main` @ `4df036c`: [37413020925](https://github.com/astraDukoWave/pcre-learning-platform/actions/runs/37413020925) ✅ | segunda pasada con la lista del contrato §12 (5 ajustes); U1 y diagnóstico en `ready-for-review`; `docs/contenido/revision/{u1,inicial}.md` generados y comprobados en la CI; `make verify` exit 0 (274 pruebas backend); fuentes de coe.int y cambridge.org siguen `pending` (la sesión no llega a esos hosts) | 6 oct 2026 |
| MVP-01 | CS-12 · cierre (verify + activación) | `docs/mvp01-cs12-close` | [#14](https://github.com/astraDukoWave/pcre-learning-platform/pull/14) | `211c53f` (head `b562c0c`) | [37415037630](https://github.com/astraDukoWave/pcre-learning-platform/actions/runs/37415037630) ✅ 8 jobs + ci-gate | `make verify` exit 0 en un clon limpio de `4df036c` tras el hook de arranque (AC-01); `docs/reviews/mvp-01-verify.md`, `docs/reviews/mvp-01-activacion-cto-review.md`, README, HANDOFF, AGENTS y runbook (§12, H-6); verificador independiente: 1 bloqueante (clave siempre en `a`), 3 de cobertura o NFR-01 y 4 observaciones, corregidos en el PR (`make verify` exit 0, 284 pruebas backend, 25 Vitest; E2E 13/13 local) | 6 oct 2026 |
| MVP-02 | CS-01 · presupuestos y consumo | `feat/mvp02-cs01-usage` | [#15](https://github.com/astraDukoWave/pcre-learning-platform/pull/15) | `6577467` (head `f8f8459`) | [37515756992](https://github.com/astraDukoWave/pcre-learning-platform/actions/runs/37515756992) ✅ 8 jobs + ci-gate | migración `usage_v1`; reservas con bloqueo global → alumno; AC-01 con dos hilos contra PostgreSQL; vista `/admin/consumo` con aviso al 80 %; `make verify` exit 0 (293 pruebas backend, 28 Vitest, 6 migraciones nuevas); NI-05 | 6 oct 2026 |
| MVP-02 | CS-02 · evaluador de feedback y set de evaluación | `feat/mvp02-cs02-feedback-eval` | [#16](https://github.com/astraDukoWave/pcre-learning-platform/pull/16) | `304c6da` (head `5a8a3ed`) | [37549251549](https://github.com/astraDukoWave/pcre-learning-platform/actions/runs/37549251549) ✅ 8 jobs + ci-gate | `make verify` exit 0 (325 pruebas backend); AC-03 con salidas rotas, evidencia inventada, URLs y puntajes en español, campos de más; AC-05 offline: 27 casos, referencia ✅, adversarial y con contradicciones ❌; `feedback-eval.yml` con actionlint; [verificador independiente](https://github.com/astraDukoWave/pcre-learning-platform/pull/16#issuecomment-6027722929): 4 bloqueantes y 13 menores corregidos en `e288bb4`/`5456e02`; NI-06, NI-07 | 6 oct 2026 |
| MVP-02 | CS-03 · feedback de escritura de extremo a extremo | `feat/mvp02-cs03-writing-feedback` | [#17](https://github.com/astraDukoWave/pcre-learning-platform/pull/17) | `fd68ce4` (head `8940117`) | [37549544782](https://github.com/astraDukoWave/pcre-learning-platform/actions/runs/37549544782) ✅ 8 jobs + ci-gate | `make verify` exit 0 (334 pruebas backend, 32 Vitest); AC-04: misma llave y peticiones posteriores no cobran dos veces, `unknown` conserva la reserva y no se reintenta, `failed` libera y permite reintentar; no evaluable sin repaso; 👍/👎 por observación con dueño; repaso por dificultad confirmada; AC-02 (parte de escritura): 503 esperado sin capacidad o presupuesto y E2E con la autoevaluación como alternativa; E2E del feedback con el evaluador falso | 6 oct 2026 |
| MVP-02 | CS-04 · transcripción de grabaciones | `feat/mvp02-cs04-transcription` | [#18](https://github.com/astraDukoWave/pcre-learning-platform/pull/18) | `8dc7ef7` (head `c9a819b`) | [37551177973](https://github.com/astraDukoWave/pcre-learning-platform/actions/runs/37551177973) ✅ 8 jobs + ci-gate | `make verify` exit 0 (357 pruebas backend, 37 Vitest); AC-06: el audio nunca toca disco (prueba con escritura a disco y temporales bloqueados, 1.5 MB), 413 y 422 por tamaño, tipo y duración, comparación de la repetición con fixtures; entrevista confirmada o disputada antes del feedback; idempotencia, `unknown` sin reintento y `failed` reintentable; AC-02 (transcripción): 503 esperado y sin botón con la capacidad apagada; E2E grabar → transcribir (falso) → comparar y entrevista → feedback; NI-08 | 7 oct 2026 |
| MVP-02 | CS-05 · sesiones de voz: backend y Deepgram falso | `feat/mvp02-cs05-voice` | [#19](https://github.com/astraDukoWave/pcre-learning-platform/pull/19) | `3425803` (head `9c3bb62`) | [37579375341](https://github.com/astraDukoWave/pcre-learning-platform/actions/runs/37579375341) ✅ 8 jobs + ci-gate | `make verify` exit 0 (399 pruebas backend, 7 migraciones nuevas probadas); migración `voice_v1`; AC-07 (Origin ajeno, sesión ajena y segunda conexión rechazadas antes de `accept()`; 409 y 503 de cupo), AC-08 (con `VOICE_MAX_SESSION_S=3` el falso registra el cierre a 3 ± 0.5 s; `ended(deadline)` y conciliación), AC-09 (desconexión → proveedor cerrado en ≤ 2 s; logout), AC-10 (barrido de huérfanas), AC-11 (ayudas con hora; `InjectUserMessage` y `UpdatePrompt`), sin consentimiento solo duración y ayudas, `KeepAlive`, silencio y límites por segundo; un WebSocket ya no se registra como 500 en `error_events`; con el Deepgram falso (`tests/fakes/deepgram_agent.py`); verificador independiente: ronda 1 con 2 bloqueantes (stop durante el arranque del relay; una tarea que muere deja sin deadline) y 6 menores corregidos con pruebas; ronda 2 (4 lentes, sobre `bbbdad7`) sin bloqueantes, con los 8 arreglos confirmados y menores corregidos: stop y `claim()` bajo el mismo lock, `PENDING_STOP` limpio, rollback con `VOICE_ENABLED` apagado también en el WebSocket, tiempo conectado al proveedor conciliado, duración con tope, aborto de un proveedor que no contesta el cierre, ecos de «repetir» contados, `ended` aunque falle el cierre en la base, `sample_rate` en `ready`, y 14 pruebas nuevas (stop con relay vivo, timeout de conexión, logout por mensaje de control, cupo concurrente, gracia, margen del barrido, frames grandes, guardas de producción); NI-09 | 7 oct 2026 |
| MVP-02 | CS-06 · pantalla del coach | `feat/mvp02-cs06-coach-screen` | [#20](https://github.com/astraDukoWave/pcre-learning-platform/pull/20) | `33a556f` (head `fca4a85`) | [37613132336](https://github.com/astraDukoWave/pcre-learning-platform/actions/runs/37613132336) ✅ 8 jobs + ci-gate | `make verify` exit 0; Vitest del remuestreo a 16 kHz, PCM16 en frames de 40 ms y la máquina de estados; E2E `test_voice_coach.py` con el micrófono falso de Chromium y el Deepgram falso (aviso de Deepgram, consentimiento, Conectando/Te escucho/El coach está hablando, subtítulos `aria-live`, «Repetir», «Detener», resumen) y modo texto con la voz apagada; la cola de 24 kHz se vacía con `UserStartedSpeaking` y usa la frecuencia que anuncia `ready`; el worklet y las fuentes salen como archivos (la CSP no permite `data:`); fin al pasar a segundo plano; capturas `coach-*.png` revisadas | 7 oct 2026 |
| MVP-02 | CS-07 · feedback final de voz, repasos, observabilidad y E2E | `feat/mvp02-cs07-voice-feedback` | se completa al abrir | se completa al mergear | se completa al terminar | `make verify` exit 0; feedback final con la rúbrica del escenario (≥ 30 s de voz y consentimiento; hasta 2 observaciones con evidencia dentro de un turno; misma reserva, idempotencia y política de `unknown` que REQ-02) y repaso por dificultad confirmada; «Eso no fue lo que dije» oculta las observaciones del turno (AC-13); exportación y borrado con transcripciones (AC-12); valoración de la sesión; log `voice_session_started` con escenario y `user_ref` sin texto de la transcripción (REQ-07); panel del piloto con minutos, sesiones, cierres, llamadas, costo del mes, turnos disputados y valoración; E2E de AC-14 con un WAV como micrófono falso y el Deepgram falso (audio del coach, transcripción, «Repetir», «Detener», evidencia resaltada, disputa y valoración) y modo texto con la voz apagada; grep de llaves en el bundle (`make frontend-check`) y en los mensajes (AC-15); memoria con 3 sesiones y frames de 1 MiB: 110.5 MB en reposo, pico 124.6 MB < 300 MB (AC-16, `scripts/perf/voice_memory.py`); accesibilidad del coach con teclado, axe y movimiento reducido (NFR-08); el coach acaba su frase en ≤ 2 s al terminar (EDGE-13); verificador independiente (4 lentes: spec, dinero, privacidad e interfaz): 1 bloqueante (dos peticiones de feedback con claves distintas pagaban dos llamadas; ahora una sola ejecución por sesión dentro de la reserva) y los menores corregidos con pruebas (marcas concurrentes con lock, disputa durante la evaluación, repaso deshecho si una disputa deja sin observaciones, resultado pagado reconstruido, clave revisada primero, huérfanas a `unknown`, 👍/👎 en voz, tope del mes en el panel, llave de 40 hex en el grep del bundle, resaltado como el validador, reintentos sin callejones, región viva y foco); NI-10 | 7 oct 2026 |

## Desviaciones

Ninguna.

## Notas de interpretación (no cambian alcance; confirmación opcional de Jonathan)

- **NI-01 · Bloque PCRE en el DTO de la lección** (verificador de CS-04, PR #6). La lección
  muestra su explicación breve PCRE (patrón, concepto, reglas, dos ejemplos y tarea de
  aplicación) antes de practicar: el contrato §5 la exige como contenido de la lección.
  AC-08 se aplica a lo que es de cada ítem: su `explanation_es`, su clave, variantes,
  pistas, apoyo, transcripción, ejemplo (`example`, la ayuda de REQ-11) y rúbrica, que solo
  viajan después de enviar o por `POST /aids`. Regla editorial asociada: el patrón y los
  ejemplos de la explicación no deben resolver un ítem (lista de revisión, contrato §12).

- **NI-02 · Autoevaluación después de enviar** (CS-06). REQ-10 pide la autoevaluación con
  la rúbrica *después* de enviar, y AC-08 impide que la rúbrica viaje antes. El intento de
  `short_writing` y `recorded_speaking` se crea `pending` y devuelve la rúbrica; la
  autoevaluación se guarda con `POST /api/v1/attempts/{id}/self-assessment` (no estaba en
  la tabla de rutas de `docs/arquitectura.md`). Solo pasa `pending → evaluated` con
  `evaluation_source = self`; no toca la respuesta guardada; repetir con las mismas marcas
  devuelve lo mismo y con otras marcas responde 409 (para cambiar de opinión se reformula
  con `revision_of`). Es el mismo patrón que `POST /attempts/{id}/feedback` de MVP-02.

- **NI-03 · Rutas auxiliares de comprobaciones** (CS-07). Además de las rutas de la tabla
  de `docs/arquitectura.md`, REQ-12 necesita dos que no estaban listadas:
  `GET /api/v1/assessments/{form_id}` (formulario, corridas numeradas y si se puede
  iniciar; la pantalla de inicio la usa para retomar o mostrar resultados) y
  `POST /api/v1/admin/users/{user_id}/diagnostic-reset` ("un admin puede reiniciarlo",
  EDGE-09). El reinicio deja la corrida en el historial con `reset_at`; no guarda quién lo
  hizo en la tabla (toda FK a `users` es `CASCADE`, regla de `data_registry`): queda en el
  log `diagnostic_reset` con el `user_ref` del admin. Un ítem cuyo audio no cargó se guarda
  con `audio_failed` y queda "no evaluable (audio)" fuera del denominador (EDGE-07).

- **NI-04 · `GET /api/v1/legal`** (CS-10). REQ-17 pide mostrar en el aviso el contacto de
  `PRIVACY_CONTACT_EMAIL`, que vive en la configuración del servidor. Ruta pública de solo
  lectura con `consent_version` y ese contacto; no estaba en la tabla de rutas.

- **NI-05 · 503 esperados fuera de `error_events`** (MVP-02 CS-01). `capability_disabled` y
  `budget_exhausted` son respuestas previstas por el spec (se registran como `info` en el
  log), no errores del servidor: el manejador marca la petición y el registro de 5xx de
  MVP-01 las omite. Los demás 503 (base de datos, migración) se siguen registrando.
- **NI-06 · Gemini por REST** (MVP-02 CS-02). El plan (D5) menciona el SDK `google-genai`;
  el adaptador llama a `generateContent` por HTTP con `httpx` (salida JSON con
  `responseSchema`, plazo total de 20 s con `app/core/deadline.py`), sin dependencia nueva y
  probado con un transporte simulado. Las salidas de referencia del set de evaluación están
  escritas a mano con la forma de la salida del modelo: no son grabaciones de un modelo real
  (eso es G5a).
- **NI-07 · Guardas de la regla de selección** (MVP-02 CS-02, verificador independiente). La
  regla del spec (0 contradicciones, evidencia válida ≥ 95 %, p95 ≤ 12 s) la cumplía un modelo
  que siempre devuelve vacío o siempre se abstiene, y no medía la inyección. `evals/run.py`
  además exige 0 salidas inválidas, estado y motivo esperados en ≥ 90 % de los casos, 0 URLs o
  puntajes devueltos y, en los casos de inyección, el estado y los criterios esperados; la
  evidencia sin observaciones vale 0. Una variante válida citada dentro de una evidencia más
  larga deja al modelo "revisar": no se elige solo y lo decide quien firma G5a. Cada caso
  declara `max_observations` (REQ-03). Antes del run de G5a, Jonathan confirma que
  `GEMINI_API_KEY` existe **solo** como secret del environment `evals` (no del repo ni de la
  organización) y que `evals` tiene revisor obligatorio.

- **NI-08 · Rutas auxiliares de REQ-04** (MVP-02 CS-04). Además de
  `POST /speaking/transcriptions`: `POST /attempts/{id}/transcription` (`{"confirmed": bool}`)
  guarda "Eso no fue lo que dije" o la confirmación de la entrevista, sin costo; y
  `GET /capabilities` (alumno) dice solo si feedback, transcripción y voz están encendidos, para
  que la interfaz no envíe el audio cuando la transcripción está apagada. El formulario
  multipart se lee en memoria con el parser de bajo nivel de `python-multipart`
  (`app/http/multipart.py`), porque `UploadFile` pasa a disco desde 1 MB.

- **NI-09 · Detalles de la sesión de voz** (MVP-02 CS-05). (1) `POST /voice-sessions` recibe,
  además de `scenario_id`, `accept_voice_notice` (registra `users.voice_notice_accepted_at`
  la primera vez; sin aviso aceptado → 422) y `save_transcript` (el consentimiento por
  sesión). (2) `deadline_at` = creación + máximo + 30 s de gracia, como pide REQ-05; la
  conversación dura el máximo desde `SettingsApplied` y nunca pasa de `deadline_at`, así la
  reserva (máximo × precio) cubre lo facturable. (3) El 503 "Intenta en unos minutos"
  (`voice_busy`) es esperado como los de NI-05: no entra a `error_events`. (4) La forma de
  `Settings`, `InjectUserMessage`, `UpdatePrompt`, `InjectAgentMessage` y `KeepAlive` sigue la
  referencia de la Voice Agent API citada en el spec; el dominio de Deepgram está bloqueado
  por el proxy de esta sesión, así que la forma exacta se confirma en la prueba manual de G5
  `[inherited-unverified]`. (5) `VOICE_PROVIDER=fake` y `VOICE_AGENT_URL` (solo `ws://`
  localhost) conectan con el Deepgram falso; ambos están prohibidos en producción.
  (6) Conciliación: se cobra el mayor entre fin − inicio y el tiempo conectado al proveedor
  (Deepgram cobra la conexión), hasta el máximo reservado; una sesión que se conectó al
  proveedor pero no llegó a empezar concilia ese tiempo (no se asume consumo cero), y solo
  sin conexión se libera la reserva. La duración que ve el alumno nunca pasa del máximo.

- **NI-10 · Feedback final de voz** (MVP-02 CS-07). (1) La revisión de un escenario guarda solo
  el id de su rúbrica; los criterios se leen de `CONTENT_DIR/*/rubrics.yaml`, el mismo
  directorio que importa la release. Sin rúbrica no se llama al proveedor (`failed`,
  `rubric_missing`). (2) Rutas: `POST /api/v1/voice-sessions/{id}/feedback`
  (`Idempotency-Key`; 409 si la sesión sigue abierta) y
  `POST /api/v1/voice-sessions/{id}/turns/{n}/flag` (la de `docs/arquitectura.md`; solo
  turnos propios; idempotente). La pantalla pide el feedback una vez al terminar. (3) Los 30 s de voz se miden de
  `UserStartedSpeaking` al `ConversationText` del alumno, sin los ecos de «repetir»
  (`learner_speech_ms`); el mínimo es configurable (`VOICE_MIN_LEARNER_SPEECH_S`, 1 s en el E2E).
  (4) Se evalúan solo los turnos del alumno sin ayudas, unidos por ` | ` como dice el prompt
  `voice-v1`. Una observación cuya evidencia cruza turnos se descarta (no se puede resaltar ni
  disputar); si no queda ninguna, el resultado es `not_evaluable/no_valid_evidence`. (5) La
  dificultad se confirma al guardar el resultado, con los turnos disputados en ese momento, y
  programa el repaso de los objetivos del escenario. Si una disputa posterior deja sin
  observaciones visibles, el repaso vuelve al estado anterior, salvo que otra práctica lo haya
  movido: la disputa es un problema de reconocimiento, no un error del alumno. (7) Una sesión
  tiene una sola ejecución de feedback que no falló: la revisión va dentro de la reserva, con
  el lock global, así que dos peticiones con claves distintas a la vez no pagan dos llamadas
  (lo mismo para el feedback de escritura y la transcripción de un intento). El barrido al
  arrancar pasa a `unknown` las ejecuciones de feedback o transcripción abiertas por más de
  10 min (una caída a mitad de la llamada). (6) La valoración de la sesión usa el contexto
  `voice` de `user_feedback`, que ya permitía la tabla, con 404 si la sesión es ajena. El panel
  cuenta los turnos disputados como problemas de reconocimiento, nunca su texto.

## Loop humano vigente

No bloquea MVP-02: el agente sigue con su plan mientras tanto.

1. **H-1b** — https://github.com/astraDukoWave/pcre-learning-platform/settings/rules →
   ruleset `main` → **Require status checks to pass** → **Add checks** → `ci-gate` →
   **Save changes**. Devuélveme: "ci-gate requerido".
2. **G1–G4** — en orden, con `docs/reviews/mvp-01-activacion-cto-review.md` (mensajes de
   aprobación listos para pegar) y `docs/runbook.md`. Devuélveme: las URLs y salidas que pide
   cada mensaje.

*Última actualización: 6 oct 2026 (cierre de MVP-01).*
