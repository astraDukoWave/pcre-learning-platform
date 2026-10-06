# Dictamen CTO: activación de MVP-01 — gates G1 a G4

- **Ciclo:** MVP-01 · Núcleo y piloto U1.
- **Artefactos revisados:** spec `docs/specs/mvp-01-nucleo-piloto.md` @ `9aa2e2c`; código,
  contenido y workflows en `main` @ `4df036c` (tras CS-11); `docs/runbook.md`,
  `.github/workflows/deploy.yml`, `heroku.yml`, `Dockerfile`, `docs/reviews/mvp-01-verify.md`,
  `docs/reviews/mvp-01-seguridad.md` y `docs/reviews/mvp-01-perf-smoke.md` (rama de CS-12).
- **Fecha:** 6 oct 2026. Formato: skill `cto-review` según `docs/sdd/proceso.md` §9.
- **Firma:** Jonathan, un gate a la vez. Este dictamen no aprueba por él y el agente no
  ejecuta ninguna de estas acciones.

## Clasificación por acción

| Acción | Clase | Gate | Quién la ejecuta |
|---|---|---|---|
| Crear la app de Heroku, Postgres Essential-0, config vars y el token de deploy | Alto (secretos y dinero) | G1 | Jonathan (runbook §1) |
| Crear el environment `production` con revisor, el secret y `DEPLOY_ENABLED` | Alto (permisos) | G1 | Jonathan (runbook §2) |
| Aprobar el primer deploy y los siguientes | Alto (producción) | G1 | Jonathan (runbook §3) |
| Migrar una base que después tendrá datos reales | Alto (datos) | G1 | `deploy.yml` tras la aprobación: backup previo + migraciones *expand* |
| Generar el audio de U1 y del diagnóstico con TTS | Alto (dinero, acotado) | G2 | Jonathan aprueba `content-audio.yml` (runbook §8) |
| Revisar y publicar U1 y el diagnóstico | Alto (impacto educativo) | G3 | Jonathan en el panel (runbook §9) |
| Aprobar los textos legales, ensayar la restauración e invitar alumnos reales | Alto (datos personales) | G4 | Jonathan (runbook §5 y §10) |
| Prueba manual en iPhone y Android (H-6) | Rutina (verificación) | Antes de G4 | Jonathan (runbook §12) |

## Verificaciones (matriz)

| Claim | Fuente | Resultado |
|---|---|---|
| La CI completa (8 jobs + `ci-gate`) pasa en cada PR de MVP-01 | Runs ligados al SHA en `STATE.md` | `[ci-run]` |
| La imagen de producción construye, migra con el comando `release` y arranca con `run.web`; `/health`, `/ready`, `/`, 404 JSON y asset inexistente | Job `image` (`scripts/ci/image-smoke.sh`) | `[ci-run]` |
| `deploy.yml` se omite sin `DEPLOY_ENABLED` y no queda en verde | Run [37412451354](https://github.com/astraDukoWave/pcre-learning-platform/actions/runs/37412451354) en `main` @ `33b14f1`: `skipped` | `[verified-this-session]` |
| `deploy.yml` falla con "deploy no configurado" sin secret o variable | Lectura del workflow; actionlint limpio | `[verified-this-session]` por inspección; la ejecución se comprueba en G1 (runbook §2.3) |
| El helper de credenciales de git entrega el token sin escribirlo en disco ni en la URL | `git credential fill` con un valor de prueba | `[verified-this-session]` |
| Las migraciones son *expand*: el código anterior funciona con el esquema nuevo | Job `migrations` (vacía→head, legado+seed→head, downgrade/upgrade, `alembic check`) | `[ci-run]` |
| p95 < 800 ms con 10 concurrentes en los cinco endpoints de NFR-03 | `docs/reviews/mvp-01-perf-smoke.md` (build de producción local) | `[verified-this-session]`; en Heroku no se ha medido |
| Seguridad de §7 (sesiones, CSRF, Origin, cabeceras, CSP, límites, Markdown) | `docs/reviews/mvp-01-seguridad.md` con la prueba de cada control | `[ci-run]` |
| Ninguna llamada de pago en CI ni en desarrollo | Guard de red de pytest (`tests/test_network_guard.py`) y dobles de TTS | `[ci-run]` |
| Ruleset de `main` activo | `rules/branches/main` → `deletion`, `non_fast_forward`, `pull_request` | `[verified-this-session]`; **sin** `required_status_checks` (H-1b pendiente) |
| Heroku acepta `heroku.yml` con `release` e `image: web`; Essential-0 sin rollback | devcenter.heroku.com (G0) | `[inherited-unverified]` desde G0; la sesión no llega a Heroku |
| Comandos de la CLI de Heroku del runbook (`addons:wait`, `pg:backups:schedule`, `releases:output`, `ps:type`) | Conocimiento del agente; la sesión no puede correr la CLI | `[inherited-unverified]`: Jonathan los confirma al ejecutarlos |
| Fuentes de Cambridge y del Consejo de Europa citadas en U1 | El proxy de la sesión bloquea esos hosts | Quedan `pending` en `sources.yaml` y en el paquete de revisión |
| Audio de U1 y del diagnóstico | Guiones en `audio/manifest.yaml`; sin MP3 | Pendiente de G2; el lint bloquea aprobar y publicar mientras tanto |

## Veredicto: APROBAR CON CAMBIOS

La plataforma está lista para G1. Los cambios son pasos de configuración y de orden; no
hace falta tocar código.

1. **Hacer H-1b antes de G1: `ci-gate` como check requerido del ruleset de `main`.**
   *Por qué:* hoy un PR podría mergearse con la CI en rojo si alguien se equivoca; con G1,
   `main` es lo que se despliega. `deploy.yml` ya exige un CI exitoso, pero el check
   requerido protege también los merges.
2. **Cargar el secret `HEROKU_API_KEY` solo después de la regla de revisor del environment
   `production`, y `DEPLOY_ENABLED=true` al final** (runbook §2). *Por qué:* un environment
   que no existe se crea sin protección la primera vez que un workflow lo usa.
3. **G3 incluye confirmar las fuentes `pending`** (Cambridge y Consejo de Europa) o pedir
   otras. *Por qué:* el contrato §12 exige fuente por regla; la sesión no pudo consultarlas
   y no las marca como verificadas.
4. **G4 exige, en este orden:** textos legales aprobados y `CONSENT_VERSION` igual a su
   encabezado, ensayo de restauración con resultado en `STATE.md`, y la prueba H-6 en
   teléfonos. *Por qué:* son las tres condiciones que el spec pone antes de guardar datos de
   personas reales.

## G1 · Deploy a Heroku

- **Qué autoriza:** crear la app y desplegar `main` cada vez que apruebes un run de
  `deploy.yml`.
- **Pasos exactos:** runbook §1 (Heroku), §2 (GitHub, con la comprobación de "deploy no
  configurado"), §3 (aprobación, verificación y dyno Basic) y §4 (tu admin).
- **Rollback:** `heroku rollback v<N> --app <app>` (segundos; las migraciones son *expand*).
  Si un rollback cruza una migración, `/api/v1/ready` responde 503 `migration_mismatch`
  hasta el siguiente deploy: es esperado y la app sigue sirviendo (runbook §6).
- **Blast radius:** la app y su base. Antes de G4 no hay datos de personas: solo tu cuenta
  admin y el contenido en borrador. Costo: dyno Basic y Essential-0 con tus créditos.
- **Dueño:** Jonathan aprueba cada deploy; el workflow lo ejecuta.
- **Observabilidad:** resumen del run (SHA, release, smoke), `heroku releases`,
  `heroku logs` (JSON con `request_id`), `/api/v1/ready` con la migración head y la pestaña
  Errores de `/admin/piloto`.
- **Evidencia que me devuelves:** URL del run "deploy no configurado" (AC-21), URL del
  primer run de deploy en verde y la salida de `curl -s https://<host>/api/v1/ready`.

## G2 · Audio de U1 y del diagnóstico

- **Qué autoriza:** un run de `content-audio.yml` por prefijo (`u1` e `inicial`), con tope
  de caracteres.
- **Pasos exactos:** runbook §8. Costo estimado con `--dry-run` sobre `main` @ `4df036c`
  `[verified-this-session]`: U1, 12 guiones, 1 493 caracteres, USD 0.0448; diagnóstico, 3
  guiones, 985 caracteres, USD 0.0295 (precio de Aura-2 del 5 oct 2026; reconfírmalo).
  Tope sugerido: `max_chars=20000` por run.
- **Rollback:** cerrar el PR del audio sin mergear; si ya se mergeó, revertirlo con un PR.
  Lo gastado no se recupera, pero está acotado por el tope.
- **Blast radius:** el costo del run y los MP3 del PR. Nada llega a alumnos sin G3.
- **Dueño:** Jonathan aprueba el environment `content-audio` y escucha cada archivo.
- **Observabilidad:** resumen del run (conteo, costo estimado, archivos), el PR con los MP3
  y el lint (`pending_audio` desaparece cuando `reviewed_by` está lleno).
- **Evidencia que me devuelves:** URL de los runs y de los PR mergeados.

## G3 · Publicación de U1 y del diagnóstico

- **Qué autoriza:** aprobar por hash y publicar las seis piezas de U1 y el diagnóstico.
- **Pasos exactos:** runbook §9 con `docs/contenido/revision/u1.md` y
  `docs/contenido/revision/inicial.md` (lista §12 por ítem; hashes iguales a los del panel).
  Los hallazgos se registran en el panel; el agente los corrige en una revisión nueva.
- **Rollback:** "Retirar" la revisión publicada o volver a publicar la anterior; los
  intentos conservan su revisión (AC-11).
- **Blast radius:** lo que ven tus alumnos internos (y, tras G4, los reales).
- **Dueño:** Jonathan; el agente nunca aprueba ni publica.
- **Observabilidad:** bitácora editorial del panel, reportes de contenido en
  `/admin/reportes` y valoraciones por lección en `/admin/piloto`.
- **Evidencia que me devuelves:** el tiempo que te tomó revisar U1 (métrica del spec) y los
  hallazgos registrados, si hubo.

## G4 · Alumnos reales

- **Qué autoriza:** invitar a las primeras 2–3 personas y guardar sus respuestas.
- **Pasos exactos, en orden:** aprobar los textos legales (PR que cambia el encabezado de
  `apps/frontend/src/legal/*.md` y quita "Borrador pendiente de revisión"), poner
  `CONSENT_VERSION` igual en Heroku, ensayar la restauración (runbook §5), hacer H-6 (runbook
  §12) e invitar desde `/admin/usuarios` (runbook §10).
- **Rollback:** "Cerrar sesiones" y borrar la cuenta (el alumno también puede borrarla desde
  su perfil; AC-22); restauración de datos con el procedimiento del runbook §6.
- **Blast radius:** datos personales de las personas invitadas (correo, respuestas y
  grabaciones que **no** salen del dispositivo en MVP-01).
- **Dueño:** Jonathan (invita, responde a solicitudes de datos y es el contacto de
  privacidad).
- **Observabilidad:** `/admin/piloto` (activos, intentos, lecciones, valoraciones,
  errores), `heroku logs` sin correos (`user_ref`) y los eventos de producto.
- **Evidencia que me devuelves:** fecha del ensayo de restauración con su resultado,
  checklist H-6 y el número de invitaciones enviadas.

## Decisiones que son tuyas

1. **¿Mantienes el contenido y las claves en el repo público durante el piloto?**
   - *TL;DR:* las respuestas de U1 y del diagnóstico son legibles en GitHub. Con 2–3
     personas conocidas y uso formativo, el riesgo es bajo; el trigger de
     `docs/arquitectura.md` §2 ya dice sacarlas a partir de 10 alumnos externos (LB-09).
   - *Ganas:* el flujo actual (contenido como código, revisión por PR) sin cambios.
   - *Pagas:* alguien curioso puede ver las claves antes de responder.
   - *Recomendación:* sí durante el piloto, con el trigger tal como está.
   - **Pregunta cerrada:** ¿sí o no?
2. **¿Con qué nombre sale la app en G1?**
   - *TL;DR:* `APP_NAME` aparece en la interfaz; "PCRE" choca en buscadores con la librería
     de expresiones regulares (LB-05).
   - *Ganas:* si eliges otro nombre ahora, tus primeras alumnas no ven un cambio después.
   - *Pagas:* nada en código: es una config var.
   - *Recomendación:* `APP_NAME=PCRE` para el piloto; el nombre comercial con LB-05.
   - **Pregunta cerrada:** ¿PCRE u otro nombre?
3. **¿Haces la prueba en teléfonos (H-6) antes de invitar, o en paralelo con la primera
   alumna?**
   - *TL;DR:* MediaRecorder en Safari iOS es el supuesto técnico más frágil del ciclo; la CI
     lo cubre con Chromium, no con un iPhone real.
   - *Ganas* (antes): nadie se topa con una grabación que no funciona.
   - *Pagas:* unos 20 minutos antes de invitar.
   - *Recomendación:* antes de G4.
   - **Pregunta cerrada:** ¿antes o en paralelo?

## Mensajes de aprobación (pegar en la sesión, uno por gate)

> **G1:** Apruebo G1 para MVP-01 @ `<SHA de main>`: creé la app `<app>` (Cedar, stack
> container, Postgres Essential-0 con backups diarios), el environment `production` con mi
> revisión obligatoria, el secret `HEROKU_API_KEY` y las variables `HEROKU_APP_NAME` y
> `DEPLOY_ENABLED=true`. Run "deploy no configurado": `<URL>`. Primer deploy aprobado:
> `<URL>`; `/api/v1/ready` → `<salida>`. H-1b hecho: `ci-gate` es check requerido.
> Decisiones: 1 `<sí/no>` · 2 `<nombre>` · 3 `<antes/en paralelo>`.

> **G2:** Apruebo G2 para el audio de `u1` e `inicial` con `max_chars=<n>`: runs `<URL>`,
> PRs `<URL>` revisados por mí (`reviewed_by` lleno).

> **G3:** Apruebo G3: revisé U1 y el diagnóstico con los paquetes de revisión en `<tiempo>`;
> fuentes pendientes `<confirmadas | hallazgos registrados>`; publiqué las revisiones con
> hash `<hashes>`.

> **G4:** Apruebo G4: textos legales aprobados con versión `<versión>` (= `CONSENT_VERSION`);
> ensayo de restauración del `<fecha>` con resultado `<ok>`; H-6 `<ok | hallazgos>`; invito a
> `<n>` personas.

## Registro del gate

```json
{
  "cycle": "MVP-01",
  "review": "activation",
  "date": "2026-10-06",
  "verdict": "approve_with_changes",
  "changes": ["H-1b before G1", "reviewer rule before secret", "pending sources in G3", "legal + restore + H-6 before G4"],
  "gates": {
    "G1": {"status": "not_started", "owner": "Jonathan", "runbook": ["§1", "§2", "§3", "§4"]},
    "G2": {"status": "not_started", "owner": "Jonathan", "runbook": ["§8"]},
    "G3": {"status": "not_started", "owner": "Jonathan", "runbook": ["§9"]},
    "G4": {"status": "not_started", "owner": "Jonathan", "runbook": ["§5", "§10", "§12"]}
  },
  "decisions_open": ["public answer keys during pilot", "APP_NAME at G1", "H-6 timing"]
}
```
