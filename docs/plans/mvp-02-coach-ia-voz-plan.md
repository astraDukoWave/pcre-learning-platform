# Plan: mvp-02-coach-ia-voz

- **plan_id:** MVP-02-PLAN-01
- **Spec:** `docs/specs/mvp-02-coach-ia-voz.md` @ `9aa2e2c` (MVP-02-SPEC-01;
  sha256 `e425896b334f71508ae3e7a04036b5cef61c2d8501bd33d1e31b20f5f638c4b2`).
- **Precondición:** `docs/reviews/mvp-01-verify.md` sin ❌ abiertos
  (pendientes humanos permitidos).
- **Ramas:** `<tipo>/mvp02-csNN-<nombre>`, una por change set, con PR a
  `main`.
- **Lane:** **High-risk.** CS-02, CS-05 y CS-07 pasan por un verificador de
  contexto fresco antes del merge.
- **Estado:** **PENDIENTE DE APROBACIÓN** (gate G0).

---

## Contexto de dominio (con procedencia)

- **D1 · Deepgram Voice Agent API.** `wss://agent.deepgram.com/v1/agent/converse`,
  autenticación `Authorization: Token <API_KEY>`. El cliente envía primero
  `Settings` (`audio.input` con `encoding`/`sample_rate`; `audio.output`
  con `encoding`/`sample_rate`/`container`; `agent.language`,
  `agent.greeting`, `agent.listen.provider`, `agent.think.provider` y
  `agent.think.prompt`, `agent.speak.provider`) y luego audio binario.
  Mensajes del cliente: `UpdatePrompt`, `UpdateSpeak`, `UpdateThink`,
  `UpdateListen`, `InjectUserMessage`, `InjectAgentMessage`, `KeepAlive`,
  `ForceEndTurn`, `FunctionCallResponse`. Eventos del servidor: `Welcome`,
  `SettingsApplied`, `ConversationText`, `UserStartedSpeaking`,
  `AgentThinking`, `AgentStartedSpeaking`, `AgentAudioDone`,
  `PromptUpdated`, `History`, `LatencyReport`, `InjectionRefused`, `Error`,
  `Warning` y audio binario. *Fuente: developers.deepgram.com/reference/voice-agent/voice-agent,
  5 oct 2026.*
- **D2 · Modelos administrados del agente.** Proveedores `open_ai`,
  `anthropic`, `google`, `nvidia`. Nivel estándar (incluido en el precio
  por minuto): GPT-4o mini, GPT-5 nano/mini, Claude Haiku y Gemini Flash
  (`gemini-3.5-flash`, `gemini-2.5-flash`). *Fuente: developers.deepgram.com/docs/voice-agent-llm-models,
  5 oct 2026.* Los ids cambian: van en configuración y se reconfirman en
  G5.
- **D3 · Precios.** Voice Agent estándar USD 0.075/min (incluye STT, LLM y
  TTS); Nova-3 pregrabado monolingüe USD 0.0043/min; Aura-2 USD 0.030 por
  1 000 caracteres. *Fuente: deepgram.com/pricing, 5 oct 2026.*
- **D4 · Deepgram pregrabado.** `POST https://api.deepgram.com/v1/listen`
  con `model=nova-3`, `language=en`, `smart_format=true`, `punctuate=true`
  y cuerpo binario con su `Content-Type`. *Fuente: documentación de STT
  pregrabado de Deepgram; reconfirmar parámetros al implementar.*
- **D5 · Gemini.** CareerAI usa `google-genai` con
  `HttpOptions(timeout=…)` en milisegundos (verificado en 2.12.1) y el
  modelo `gemini-3.1-flash-lite`, con apagado anunciado para el 7 may
  2027; los modelos 2.x se cerraron a cuentas nuevas en julio de 2026.
  *Fuente: HANDOFF y plan C2 de CareerAI @ `0db81a1`.* La salida
  estructurada se pide con el esquema JSON del SDK y se valida igual con
  Pydantic.
- **D6 · Patrones de voz de CareerAI** @ `0db81a1`: Origin antes de
  `accept()`; límites de sesiones en el servidor; Deepgram por WebSocket
  directo con `websockets` (sin SDK) y un Deepgram falso local en las
  pruebas (`backend/tests/fake_deepgram.py`); worklet de PCM
  (`frontend/src/audio/pcm-worklet.js`) y hook que libera el micrófono al
  desmontar (`useLiveAudio.ts`); E2E con micrófono falso
  (`e2e/test_live_mode.py`); flags de uvicorn contra frames gigantes.
- **D7 · Reglas de system design aplicadas:** regla 3 (WebSocket para audio
  bidireccional); regla 5 (sin cola mientras el feedback cumpla el p95;
  trigger en `docs/arquitectura.md` §2); regla 6 (timeouts: 5 s de
  conexión, 15 s de STT y 20 s de feedback; sin reintentos de resultado
  desconocido; alternativa sin costo); regla 7 (consistencia en
  presupuesto y sesiones; disponibilidad en la práctica por texto); regla
  9 (dueño de la sesión y `Origin`); regla 10 (cuentas de Deepgram y Google
  separadas de CareerAI).

## Cumplimiento de proceso

Igual que MVP-01-PLAN-01, más:

- Verificador independiente antes del merge de CS-02, CS-05 y CS-07.
- Ninguna prueba puede abrir un socket hacia `deepgram.com`,
  `googleapis.com` ni otro proveedor (guard de red activo).
- El agente nunca corre `feedback-eval.yml` ni `content-audio.yml`: los
  dispara Jonathan (G5a y G2).

## Change sets

### CS-01 · Presupuestos y consumo

- **Archivos:** migración `usage_v1` (`budget_periods`, `ai_runs`);
  `app/modules/usage/{domain,service,models,repository,schemas,router}.py`;
  `apps/frontend/src/features/admin/usage/`; pruebas.
- **Qué hacer:** dominio de reserva, conciliación y liberación en
  micro-USD; servicio con `SELECT … FOR UPDATE` en orden global → alumno;
  `capability_disabled` sin configuración; precios por configuración;
  vista del admin con aviso al 80 %; registro en `data_registry`.
- **Verificación:** AC-01 (dos hilos contra PostgreSQL), AC-02 (parte
  backend); CI en verde.
- **Commit:** `feat(usage): budgets with atomic reservations`.

### CS-02 · Evaluador de feedback y set de evaluación

- **Archivos:** `app/modules/coaching/feedback/{ports,domain,service,prompts/}`,
  `adapters/{gemini,fake}.py`; `evals/feedback/cases/*.yaml`,
  `evals/feedback/recorded/*.json`, `evals/run.py`;
  `.github/workflows/feedback-eval.yml`; pruebas.
- **Qué hacer:**
  - Puerto `FeedbackEvaluator`; prompts versionados (escritura, entrevista
    y voz) que delimitan el texto del alumno como dato.
  - Esquema de salida de REQ-02 y validador puro: evidencia literal sobre
    el texto normalizado, máximo de observaciones, sin URLs, abstención.
  - Adaptador de Gemini con timeout de 20 s y conteo de tokens para la
    conciliación.
  - Set de 24 casos o más (REQ-03) con salidas grabadas para las pruebas
    offline. `evals/run.py` corre los casos contra un modelo real y escribe
    el reporte.
  - `feedback-eval.yml`: `workflow_dispatch`, environment `evals`, secret
    `GEMINI_API_KEY`, inputs `models` y `max_cost_usd`; sube el reporte
    como artefacto y lo resume en el run.
- **Verificación:** AC-03; pruebas offline del set; actionlint;
  verificador independiente antes del merge.
- **Commits:** `feat(coaching): feedback evaluator with evidence
  validation` · `test(evals): offline feedback evaluation set` · `ci:
  manual feedback evaluation workflow`.

### CS-03 · Feedback de escritura de extremo a extremo

- **Archivos:** endpoint `POST /attempts/{id}/feedback` y estados en
  `practice`/`coaching`; `apps/frontend/src/features/feedback/`; pruebas y
  E2E con el evaluador falso (`FEEDBACK_PROVIDER=fake` solo en `test`).
- **Qué hacer:** flujo de REQ-02 (reserva, llamada, validación, guardado,
  estados, `unknown`, reintento solo tras `failed`, reformulación, 👍/👎,
  repaso por dificultad confirmada); notas al margen con la evidencia
  resaltada; etiqueta "Feedback automático orientativo (IA)".
- **Verificación:** AC-04; E2E del feedback con evaluador falso y del modo
  deshabilitado (AC-02, parte frontend).
- **Commit:** `feat(feedback): open-response feedback end to end`.

### CS-04 · Transcripción de grabaciones

- **Archivos:** `app/modules/coaching/stt/{ports,service,adapters/{deepgram,fake}}.py`;
  dominio de comparación de la repetición; endpoint multipart (dependencia
  `python-multipart`); cambios en `recorded-speaking`; pruebas y E2E.
- **Qué hacer:** REQ-04 completo: límites (2 MB y 60 s), audio solo en
  memoria (prueba de que no se escribe a disco), `recognized_ratio`,
  disputa y confirmación de la entrevista, feedback de entrevista vía
  CS-03 y alternativa sin STT.
- **Verificación:** AC-06; E2E de grabar → transcribir (falso) → comparar.
- **Commit:** `feat(coaching): transcription for listen-and-repeat and
  interview`.

### CS-05 · Sesiones de voz: backend y Deepgram falso

- **Archivos:** migración `voice_v1` (`voice_sessions`,
  `users.voice_notice_accepted_at`);
  `app/modules/coaching/voice/{domain,service,settings_builder,relay,router,adapters/deepgram_agent}.py`;
  `apps/backend/tests/fakes/deepgram_agent.py`; pruebas.
- **Qué hacer:**
  - Crear sesión con reserva, una por alumno (índice parcial) y tres
    globales (lock consultivo).
  - WebSocket con `Origin`, dueño, una conexión, `Settings` construido
    desde el escenario, relay, `KeepAlive`, deadline del servidor, `stop`,
    desconexión, logout, silencio y ayudas → mensajes del proveedor.
  - Transcripción con consentimiento, conciliación y barrido de
    huérfanas.
  - Deepgram falso: servidor `websockets` local que emite `Welcome`,
    `SettingsApplied`, `ConversationText`, audio binario y
    `AgentAudioDone` según un guion, y registra los mensajes recibidos y la
    hora de cierre.
- **Verificación:** AC-07 a AC-11; verificador independiente antes del
  merge.
- **Commit:** `feat(voice): server-controlled voice sessions with relay`.

### CS-06 · Pantalla del coach

- **Archivos:** `apps/frontend/src/features/coach/` (pantalla, máquina de
  estados, `useVoiceCapture`, `usePcmPlayback`, worklet con remuestreo a
  16 kHz); pruebas con Vitest de las partes puras.
- **Qué hacer:** REQ-06 completo: aviso y consentimiento, captura, cola de
  reproducción vaciada al interrumpir, estados, tiempo restante, ayudas,
  detener, resumen final, disputa por turno, modo texto como alternativa y
  manejo de Safari iOS.
- **Verificación:** Vitest de la máquina de estados y del remuestreo;
  build; revisión visual con capturas en el PR.
- **Commit:** `feat(frontend): voice coach screen`.

### CS-07 · Feedback final de voz, repasos, observabilidad y E2E

- **Archivos:** cierre de sesión → evaluación con la rúbrica del escenario;
  líneas de log de REQ-07; panel del piloto; `e2e/test_voice_coach.py` y su
  WAV; `scripts/perf/voice_memory.py`; pruebas.
- **Qué hacer:** hasta dos observaciones con evidencia, turnos disputados,
  repasos por dificultad confirmada; minutos y costo en el panel; E2E de
  AC-14 (Chromium con `--use-fake-device-for-media-stream` y
  `--use-file-for-fake-audio-capture`, Deepgram falso); grep de llaves en
  el bundle y en los mensajes (AC-15); medición de memoria con tres
  sesiones (AC-16).
- **Verificación:** AC-12 a AC-16; verificador independiente antes del
  merge.
- **Commits:** `feat(voice): end-of-session feedback and reviews` ·
  `test(e2e): voice coach with fake microphone and provider`.

### CS-08 · Cierre de MVP-02

- **Qué hacer:**
  - `docs/reviews/mvp-02-verify.md` con evidencia por AC.
  - `docs/reviews/mvp-02-activacion-cto-review.md` (G5 y G5a): llaves,
    proyecto propio de Deepgram con saldo prepagado y Auto-reload apagado,
    alerta de presupuesto en Google, valores de presupuesto firmados en G0,
    flags, rollback, blast radius y peor costo diario calculado con los
    topes.
  - Aviso de privacidad actualizado (Deepgram y Google como encargados).
  - Runbook de activación y checklist de H-9; `HANDOFF.md` y `STATE.md`.
- **Verificación:** AC-17 marcado como pendiente humano; AC-18.
- **Commit:** `docs: close MVP-02 with verify report and activation review`.

## Tareas [HUMANO]

- **G5a · Benchmark del feedback.** Crear el environment `evals` con
  revisor obligatorio y luego su secret `GEMINI_API_KEY` (llave de un
  proyecto de Google solo para PCRE). Correr `feedback-eval.yml` con los
  modelos candidatos y `max_cost_usd=2`. Evidencia: URL del run y el
  reporte; el agente lo commitea en `docs/reviews/mvp-02-feedback-eval.md`.
- **G5 · Activación.** Pasos exactos en
  `docs/reviews/mvp-02-activacion-cto-review.md`.
- **H-9 · Prueba manual de voz** (después de G5), en iPhone (Safari) y
  Android (Chrome), con audífonos y sin ellos: una sesión completa, "más
  despacio", "repetir", detener, micrófono denegado, red cortada y
  deadline. Evidencia: el checklist del runbook, la latencia percibida y
  los motivos de cierre que muestra el panel.

## Orden y dependencias

```
CS-01 ─ CS-02 ─ CS-03 ─ CS-04 ─ CS-05 ─ CS-06 ─ CS-07 ─ CS-08
                    └─ G5a (cuando haya llave)            └─ G5 ─ H-9
```

## Tests requeridos

| Qué | Dónde |
|---|---|
| Reservas concurrentes y fail-closed | pytest con PostgreSQL |
| Validador del feedback con salidas grabadas y set offline | pytest |
| Benchmark con modelos reales | `feedback-eval.yml` [HUMANO] G5a |
| STT: memoria sin disco, límites, comparación | pytest |
| Voz: Origin, dueño, concurrencia, deadline, desconexión, logout, huérfanas, ayudas | pytest con Deepgram falso |
| Coach: estados y remuestreo | Vitest |
| E2E de feedback y de voz con micrófono falso | job `e2e` |
| Memoria con tres sesiones | `scripts/perf/voice_memory.py` (resultado registrado) |
| Teléfonos reales con Deepgram real | [HUMANO] H-9 |

## Riesgos → mitigación

- **Costo descontrolado** → reservas atómicas, fail-closed, topes por
  alumno y global, saldo prepagado sin Auto-reload y flags apagadas hasta
  G5.
- **Feedback que contradice una respuesta válida** → set con
  `must_not_flag`, regla de selección con 0 contradicciones y evidencia
  literal obligatoria.
- **El coach se sale del escenario o pide datos** → reglas en el prompt,
  casos de inyección y revisión en H-9; sin herramientas para el agente.
- **Audio en Safari iOS** → remuestreo en el worklet, gesto para
  `AudioContext` y modo texto siempre disponible.
- **Memoria del dyno** → flags de uvicorn, frames acotados y medición con
  tres sesiones.
- **Protocolo de Deepgram cambia** → tipos de mensaje verificados el 5 oct
  2026; el adaptador es el único que los conoce y G5 reconfirma.

## Prompt de respaldo

No va en el repo. Ver MVP-01-PLAN-01.

---

*Generado: 5 oct 2026 · Basado en MVP-02-SPEC-01 @ `9aa2e2c` · Estado:
pendiente de aprobación (G0).*
