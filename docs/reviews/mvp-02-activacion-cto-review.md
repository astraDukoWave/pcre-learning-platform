# Dictamen CTO: activación de MVP-02 — gates G5a y G5

- **Ciclo:** MVP-02 · Coach de IA y voz.
- **Artefactos revisados:** spec `docs/specs/mvp-02-coach-ia-voz.md` @ `9aa2e2c` (REQ-08,
  NFR-01 a NFR-08); código y workflows en `main` @ `{{SHA_CIERRE}}` (CS-01 a CS-07);
  `docs/runbook.md` §14 y §15, `.github/workflows/feedback-eval.yml`, `evals/README.md`, el
  aviso de privacidad (`apps/frontend/src/legal/privacidad.md`) y
  `docs/reviews/mvp-02-verify.md`.
- **Fecha:** 7 oct 2026. Formato: skill `cto-review` según `docs/sdd/proceso.md` §9.
- **Firma:** Jonathan, un gate a la vez. Este dictamen no aprueba por él y el agente no
  ejecuta ninguna de estas acciones (no crea llaves, no las lee, no dispara
  `feedback-eval.yml`, no cambia config vars ni despliega).

## Clasificación por acción

| Acción | Clase | Gate | Quién la ejecuta |
|---|---|---|---|
| Crear el proyecto de Google de PCRE, su alerta de presupuesto y la llave de la Gemini API | Alto (secretos y dinero) | G5a | Jonathan (runbook §14.1) |
| Crear el environment `evals` con revisor y su secret `GEMINI_API_KEY` | Alto (permisos y secretos) | G5a | Jonathan (runbook §14.1) |
| Disparar y aprobar `feedback-eval.yml` con `max_cost_usd=2` | Alto (dinero, acotado) | G5a | Jonathan (runbook §14.1) |
| Crear el proyecto de Deepgram de PCRE con saldo prepagado, Auto-reload apagado y su llave | Alto (secretos y dinero) | G5 | Jonathan (runbook §14.2) |
| Poner llaves, presupuestos, precios y modelo en las Config Vars de Heroku | Alto (secretos y dinero) | G5 | Jonathan (runbook §14.3) |
| Encender `AI_FEEDBACK_ENABLED`, `STT_ENABLED` y `VOICE_ENABLED` | Alto (dinero y datos personales a terceros) | G5 | Jonathan, una a la vez (runbook §14.3) |
| Prueba manual de voz en iPhone y Android (H-9) | Rutina (verificación) | Después de G5 | Jonathan (runbook §15) |
| Commitear el reporte del benchmark en `docs/reviews/mvp-02-feedback-eval.md` | Rutina (docs) | Después de G5a | El agente, con la URL del run |

## Verificaciones (matriz)

| Claim | Fuente | Resultado |
|---|---|---|
| Las tres capacidades están apagadas por omisión y fallan cerradas (503 `capability_disabled`, esperado) sin bandera, presupuesto, precio o proveedor | `tests/usage/test_budgets.py`, `tests/coaching/test_writing_feedback_api.py`, `test_transcription_api.py`, `test_voice_sessions.py` y E2E de AC-02 (`e2e/test_ai_feedback.py`, `test_formats.py`, `test_voice_coach.py`) | `[ci-run]` |
| Dos reservas concurrentes que exceden el tope: exactamente una pasa (AC-01) | `tests/usage/test_budgets.py` con dos hilos contra PostgreSQL real | `[ci-run]` |
| Reserva antes de llamar, conciliación, liberación, `unknown` contado como gastado y sin reintento automático | `tests/usage/`, `tests/coaching/test_writing_feedback_api.py`, `test_voice_feedback.py`, `test_voice_sessions.py` | `[ci-run]` |
| La voz corta en el deadline del servidor aunque el cliente se cuelgue; barrido de huérfanas; concilia el tiempo conectado al proveedor | AC-08 a AC-10 y dos rondas del verificador independiente de CS-05 | `[ci-run]` |
| Ninguna llave en el bundle ni en los mensajes al navegador ni en los logs `DEBUG` | `scripts/ci/bundle-grep.sh` (`make frontend-check`, job `frontend`) y `test_no_key_reaches_the_browser_or_debug_logs` | `[ci-run]` |
| Los dobles (`FEEDBACK_PROVIDER`, `STT_PROVIDER`, `VOICE_PROVIDER=fake`, `VOICE_AGENT_URL`) no arrancan en producción | `tests/test_settings.py::test_prod_refuses_the_fake_voice_provider_and_a_custom_agent_url` y validador de `app/core/config.py` | `[ci-run]` |
| Ninguna prueba llama a un proveedor de pago | Guard de red de pytest y dobles en `adapters/` y `tests/fakes/` | `[ci-run]` |
| Set de evaluación offline del feedback (grabado) | Job `backend` (`tests/coaching/test_eval_set.py`) | `[ci-run]`; con modelos reales es G5a |
| Memoria con 3 sesiones de voz y frames de 1 MiB: pico 124.6 MB < 300 MB | `scripts/perf/voice_memory.py` (Deepgram falso, un worker con los flags de `heroku.yml`) | `[verified-this-session]` |
| Forma exacta de `Settings`, `InjectUserMessage`, `UpdatePrompt`, `InjectAgentMessage` y `KeepAlive` frente a la Voice Agent API real | Referencia de Deepgram del 5 oct 2026 (D1 del plan); el proxy de la sesión bloquea el dominio | `[inherited-unverified]` (NI-09(4)); se confirma en H-9 |
| Precios: Voice Agent USD 0.075/min, Nova-3 USD 0.0043/min; modelo del agente en el nivel estándar | deepgram.com/pricing y la lista de modelos (5 oct 2026) | `[inherited-unverified]`; Jonathan los reconfirma en el runbook §14.2 |
| Modelo y precio de Gemini | G5a (`feedback-eval.yml`) | Pendiente de G5a |
| Los proveedores no usan los datos para entrenar (Gemini con facturación activa; Deepgram fuera de su programa de mejora de modelos) | Condiciones de cada proveedor; la sesión no llega a sus consolas | `[inherited-unverified]`; Jonathan lo confirma en el runbook §14.1 y §14.2 |
| Ruleset de `main` | `rules/branches/main` → `deletion`, `non_fast_forward`, `pull_request` | `[verified-this-session]`; **sin** `required_status_checks` (H-1b sigue pendiente) |

## Peor costo calculado con los topes (valores firmados en G0)

Topes: USD 25 al mes global (`BUDGET_GLOBAL_MONTHLY_MICROUSD=25000000`), USD 8 al mes por
alumno (`8000000`), 60 minutos de voz por alumno al mes, 3 sesiones de voz simultáneas, 5
minutos por sesión.

- **Sin topes**, la voz sola podría gastar 3 sesiones × 1 440 min/día × USD 0.075 = **USD 324
  al día**. Por eso todo pasa por una reserva antes de llamar.
- **Con los topes**, la app reserva el máximo de cada llamada antes de hacerla y rechaza la
  que no cabe. Peor día = **USD 25** (todo el mes en un día), y peor mes = USD 25.
- **Margen fuera de la reserva:** se concilia el mayor entre fin − inicio y el tiempo
  conectado, con tope en lo reservado (300 s). Por eso pueden quedar sin contar hasta unos
  7 s por sesión: la conexión previa (≤ 5 s) y el cierre (≤ 2 s). Con el tope global caben
  unas 66 sesiones de 5 minutos al mes: ≤ 66 × 7 s × USD 0.00125/s ≈ **USD 0.58 al mes**.
  Peor caso total ≈ **USD 25.6 al mes**.
- **Por alumno:** voz ≤ 60 min = USD 4.50; feedback y transcripción dentro de los USD 8.
  Con el tope global, unos 3 alumnos que agoten su tope bastan para cerrar el mes. Por
  encima de esa cifra, las capacidades se apagan solas hasta el mes siguiente y la interfaz
  ofrece la alternativa.
- **Tope del proveedor, independiente de la app:** el saldo prepagado de Deepgram con
  Auto-reload apagado (sugerido USD 10). Google no tiene tope duro, solo la alerta de
  presupuesto; el control real del feedback es la reserva de la app.

## Veredicto: APROBAR CON CAMBIOS

La plataforma está lista para G5a y, después, para G5. Los cambios son de orden y de
configuración; no hace falta tocar código.

1. **G5a antes de G5.** *Por qué:* `GEMINI_MODEL` y sus precios salen del benchmark. Sin un
   modelo que cumpla la regla de selección, `AI_FEEDBACK_ENABLED` no se enciende; la
   transcripción y la voz pueden ir sin el feedback.
2. **Proyectos y llaves propios de PCRE** (Google y Deepgram, no los de CareerAI), con
   facturación activa en Google y el saldo de Deepgram prepagado con Auto-reload apagado.
   *Por qué:* separa el gasto y el radio de una llave filtrada y pone un tope duro en el
   proveedor más caro. Además, el nivel gratuito de la Gemini API puede usar los datos
   para mejorar productos de Google, y el aviso de privacidad promete que no.
3. **El aviso de privacidad que apruebes en G4 debe ser el de este ciclo** (menciona a
   Deepgram y Google). Si invitas alumnos antes de aprobarlo, publica una versión nueva
   (encabezado y `CONSENT_VERSION`) antes de G5. *Por qué:* la app no pide volver a aceptar
   el aviso a quien ya lo aceptó; el texto aceptado tiene que nombrar a los encargados
   antes de que reciban datos.
4. **Encender una capacidad a la vez** (feedback → transcripción → voz), con la prueba mínima
   del runbook §14.3 entre cada una, y H-9 antes de anunciar la voz a los alumnos. *Por
   qué:* la forma de los mensajes de la Voice Agent API solo se confirma con el proveedor
   real.
5. **H-1b sigue pendiente.** Hazlo antes de G5 si no lo hiciste en G1. *Por qué:* con dinero
   en juego, un merge con la CI en rojo no debe ser posible.

## G5a · Benchmark del feedback

- **Qué autoriza:** un run de `feedback-eval.yml` con modelos reales y tope de USD 2.
- **Pasos exactos:** runbook §14.1.
- **Rollback:** nada que revertir: el run no toca la app. Si la llave se expuso, revócala en
  AI Studio y crea otra.
- **Blast radius:** hasta USD 2 del proyecto de Google de PCRE. Los casos del set son textos
  sintéticos, sin datos de alumnos.
- **Dueño:** Jonathan aprueba el despliegue al environment `evals`.
- **Observabilidad:** resumen del run, con el costo estimado y real por modelo y la regla de
  selección, y el artefacto `feedback-eval`.
- **Evidencia que me devuelves:** URL del run. El agente commitea el reporte en
  `docs/reviews/mvp-02-feedback-eval.md` y propone `GEMINI_MODEL` y sus precios.

## G5 · Activación de IA y voz

- **Qué autoriza:** que el feedback, la transcripción y el coach de voz lleguen a los
  alumnos, con los topes de G0.
- **Pasos exactos:** runbook §14.2 (Deepgram) y §14.3 (config vars y una capacidad a la vez).
- **Rollback:** `heroku config:set --app <app> VOICE_ENABLED=false` (o `STT_ENABLED`,
  `AI_FEEDBACK_ENABLED`). Para cortar todo el gasto,
  `heroku config:unset --app <app> BUDGET_GLOBAL_MONTHLY_MICROUSD`. Segundos, sin deploy
  (runbook §14.4). Una sesión de voz abierta se corta y se concilia con el barrido al
  arrancar.
- **Blast radius:**
  - Dinero: el peor costo calculado arriba (≈ USD 25.6 al mes); en Deepgram, como máximo
    el saldo prepagado.
  - Datos: el audio y el texto de los alumnos llegan a Deepgram; el texto o la
    transcripción, a Google. Las transcripciones y el feedback de voz se guardan solo con
    la casilla de consentimiento. La exportación y el borrado los cubren (AC-12).
- **Dueño:** Jonathan (llaves, banderas y respuesta a incidentes); el agente no ve las
  llaves.
- **Observabilidad:** runbook §14.5:
  - logs `voice_session_*`, `voice_provider_error`, `ai_run_finished` y
    `capability_disabled`, sin texto de los alumnos;
  - `/admin/consumo` (aviso al 80 %);
  - `/admin/piloto` → «Voz e IA»: minutos, sesiones, motivos de cierre, llamadas, costo,
    turnos disputados y valoración;
  - el saldo de Deepgram y las alertas de Google.
- **Evidencia que me devuelves:** salida de `/api/v1/capabilities` con las tres en `true`,
  una captura de `/admin/consumo` después de las pruebas mínimas y el checklist H-9.

## Decisiones que son tuyas

1. **¿Activas G5 antes de invitar alumnos reales (G4) o después?**
   - *TL;DR:* las banderas son globales: al encenderlas, todos los alumnos ven la IA y la
     voz.
   - *Ganas* (antes): pruebas G5 y H-9 solo con tus cuentas internas, sin datos de nadie
     más en Deepgram ni en Google.
   - *Pagas:* el gasto de tus pruebas sale del mismo tope del mes (unos USD 1–2).
   - *Recomendación:* antes de G4, con el aviso de este ciclo aprobado en G4.
   - **Pregunta cerrada:** ¿antes o después de G4?
2. **¿Cuánto saldo prepagas en Deepgram?**
   - *TL;DR:* es el único tope duro fuera de la app.
   - *Ganas* (USD 10): un error de la app no puede gastar más de eso en voz y transcripción.
   - *Pagas:* si se agota, la voz falla cerrada hasta que recargues.
   - *Recomendación:* USD 10, con una alerta de saldo bajo en Deepgram si la ofrece.
   - **Pregunta cerrada:** ¿USD 10 u otro monto?
3. **¿El coach usa el modelo por omisión (`gpt-4o-mini` de OpenAI vía Deepgram)?**
   - *TL;DR:* está en el nivel estándar, incluido en los USD 0.075/min; otro modelo puede
     cambiar el precio.
   - *Ganas:* el precio del spec y del tope.
   - *Pagas:* OpenAI interviene como subencargado de Deepgram (ya lo dice el aviso).
   - *Recomendación:* sí; si eliges otro, que sea del nivel estándar y dímelo para revisar
     el precio.
   - **Pregunta cerrada:** ¿`gpt-4o-mini` u otro?

## Mensajes de aprobación (pegar en la sesión, uno por gate)

> **G5a:** Apruebo G5a: creé el proyecto de Google de PCRE con alerta de presupuesto de USD
> 25, el environment `evals` con mi revisión y su secret. Run de `feedback-eval.yml` con
> `models=<…>` y `max_cost_usd=2`: `<URL>`. Modelo elegido: `<modelo>` a
> `<entrada>/<salida>` USD por millón.

> **G5:** Apruebo G5 para MVP-02 @ `<SHA de main>`: proyecto de Deepgram de PCRE con saldo
> de USD `<n>` y Auto-reload apagado; config vars de presupuesto (G0), precios y
> `GEMINI_MODEL=<modelo>` puestas; encendí `AI_FEEDBACK_ENABLED`, `STT_ENABLED` y
> `VOICE_ENABLED` una a la vez; `/api/v1/capabilities` → `<salida>`; H-9 `<ok | hallazgos>`.
> Decisiones: 1 `<antes/después>` · 2 `<monto>` · 3 `<modelo>`.

## Registro del gate

```json
{
  "cycle": "MVP-02",
  "review": "activation",
  "date": "2026-10-07",
  "verdict": "approve_with_changes",
  "changes": ["G5a before G5", "own Google and Deepgram projects, prepaid without auto-reload", "privacy notice of this cycle approved before any processor gets data", "one capability at a time and H-9 before announcing voice", "H-1b"],
  "worst_case_usd": {"day": 25.6, "month": 25.6, "deepgram_hard_cap": "prepaid balance"},
  "gates": {
    "G5a": {"status": "not_started", "owner": "Jonathan", "runbook": ["§14.1"]},
    "G5": {"status": "not_started", "owner": "Jonathan", "runbook": ["§14.2", "§14.3", "§14.4", "§14.5", "§15"]}
  },
  "decisions_open": ["G5 before or after G4", "Deepgram prepaid amount", "voice agent think model"]
}
```
