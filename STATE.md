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
| MVP-02 | CS-02 · evaluador de feedback y set de evaluación | `feat/mvp02-cs02-feedback-eval` | [#16](https://github.com/astraDukoWave/pcre-learning-platform/pull/16) | se completa al mergear | se completa al terminar | `make verify` exit 0 (311 pruebas backend); AC-03 con salidas rotas, evidencia inventada, URLs, puntajes y campos de más; AC-05 offline: 27 casos, referencia ✅, adversarial y con contradicciones ❌ como se espera; `feedback-eval.yml` con actionlint; verificador independiente antes del merge; NI-06 | 6 oct 2026 |

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
  `responseSchema`, timeout de 20 s), sin dependencia nueva y probado con un transporte
  simulado. Las salidas de referencia del set de evaluación están escritas a mano con la
  forma de la salida del modelo: no son grabaciones de un modelo real (eso es G5a).

## Loop humano vigente

No bloquea MVP-02: el agente sigue con su plan mientras tanto.

1. **H-1b** — https://github.com/astraDukoWave/pcre-learning-platform/settings/rules →
   ruleset `main` → **Require status checks to pass** → **Add checks** → `ci-gate` →
   **Save changes**. Devuélveme: "ci-gate requerido".
2. **G1–G4** — en orden, con `docs/reviews/mvp-01-activacion-cto-review.md` (mensajes de
   aprobación listos para pegar) y `docs/runbook.md`. Devuélveme: las URLs y salidas que pide
   cada mensaje.

*Última actualización: 6 oct 2026 (cierre de MVP-01).*
