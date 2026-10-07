# Runbook — PCRE Learning Platform

Pasos de operación para Jonathan, con el comando exacto y lo que se debe ver. El agente de
desarrollo no corre nada de esto: no despliega, no usa la CLI de Heroku, no maneja secretos,
no publica contenido ni invita personas.

Convenciones:

- `<app>` es el nombre de la app de Heroku; `<correo>`, un correo real. Los secretos nunca
  se pegan en issues, PRs, commits ni chats: van directo a Heroku o a GitHub.
- Los comandos de GitHub usan `gh` autenticado con la cuenta dueña del repo
  (`astraDukoWave/pcre-learning-platform`); cada paso indica también dónde está en la web.
- Orden de los gates: G1 (deploy) → G2 (audio) → G3 (publicación) → G4 (alumnos reales).
  La IA y la voz (G5a benchmark y G5 activación) están en las secciones 14 y 15; el dictamen
  es `docs/reviews/mvp-02-activacion-cto-review.md`.

## 1. Preparación de Heroku (G1)

1. App Cedar con stack `container`, en la región de EE. UU.:

   ```bash
   heroku create <app> --stack container --region us
   heroku apps:info --app <app>
   ```

   Se ve `Stack: container` y una `Web URL` del estilo
   `https://<app>-<hash>.herokuapp.com/`. Esa URL, sin la barra final, es `APP_ORIGIN`.

2. Postgres Essential-0 y backups diarios programados:

   ```bash
   heroku addons:create heroku-postgresql:essential-0 --app <app>
   heroku addons:wait --app <app>
   heroku pg:info --app <app>
   heroku pg:backups:schedule DATABASE_URL --at '03:00 America/Mexico_City' --app <app>
   heroku pg:backups:schedules --app <app>
   ```

   `pg:info` muestra `Plan: essential-0` y `Status: Available`; `schedules` lista el backup
   diario de las 03:00. `DATABASE_URL` la pone Heroku sola.

3. Config vars (sin MVP-02: sus banderas quedan apagadas por omisión):

   ```bash
   heroku config:set --app <app> \
     APP_ENV=prod APP_NAME=PCRE \
     APP_ORIGIN=https://<app>-<hash>.herokuapp.com \
     LOG_SALT="$(openssl rand -hex 32)" \
     CONSENT_VERSION=borrador-2026-10 \
     PRIVACY_CONTACT_EMAIL=<correo>
   heroku config --app <app>
   ```

   `CONSENT_VERSION` debe ser igual a la versión del encabezado de los textos legales
   (`apps/frontend/src/legal/*.md`). En G4, cuando apruebes el texto final, cambia el
   encabezado por PR y luego esta variable al mismo valor. `LOG_SALT` se genera ahí mismo y
   no se cambia después (cambiarlo rompe la correlación de `user_ref` en los logs).

4. Token para GitHub Actions, de larga duración y solo para el deploy:

   ```bash
   heroku authorizations:create --description "GitHub Actions deploy PCRE"
   ```

   Copia el `Token` directo al secret del paso 2.3 de la sección siguiente. No lo guardes en
   otro lugar.

## 2. Preparación de GitHub (G1)

El orden importa: un environment que no existe se crea **sin protección** la primera vez que
un workflow lo usa. Primero la regla de revisor, después el secret, al final la activación.

1. Environment `production` con revisor obligatorio (Settings → Environments → New
   environment → `production` → Required reviewers: tu usuario → Deployment branches and
   tags: Selected branches → `main` → Save protection rules). Con `gh`:

   ```bash
   gh api -X PUT repos/astraDukoWave/pcre-learning-platform/environments/production \
     -F "reviewers[][type]=User" -F "reviewers[][id]=$(gh api user --jq .id)" \
     -F "deployment_branch_policy[protected_branches]=false" \
     -F "deployment_branch_policy[custom_branch_policies]=true"
   gh api -X POST repos/astraDukoWave/pcre-learning-platform/environments/production/deployment-branch-policies \
     -f name=main
   gh api repos/astraDukoWave/pcre-learning-platform/environments/production \
     --jq '.protection_rules[] | .type'
   ```

   La última línea debe imprimir `required_reviewers` (y `branch_policy`).

2. Variable con el nombre de la app (repo → Settings → Secrets and variables → Actions →
   Variables):

   ```bash
   gh variable set HEROKU_APP_NAME --body <app> --repo astraDukoWave/pcre-learning-platform
   ```

3. Comprobación de "deploy no configurado" (AC-21), **antes** de cargar el secret:

   ```bash
   gh variable set DEPLOY_ENABLED --body true --repo astraDukoWave/pcre-learning-platform
   gh run list --workflow CI --branch main --limit 1 --repo astraDukoWave/pcre-learning-platform
   gh run rerun <id-del-run-de-CI> --repo astraDukoWave/pcre-learning-platform
   ```

   Al terminar el CI aparece un run "Deploy <sha>" esperando revisión. Apruébalo (sección
   3.2): el job falla en el paso "Configuración del deploy" con
   `deploy no configurado: falta el secret HEROKU_API_KEY …`. Anota la URL del run en
   `STATE.md`.

4. Secret del environment (Settings → Environments → production → Add environment secret):

   ```bash
   gh secret set HEROKU_API_KEY --env production --repo astraDukoWave/pcre-learning-platform
   ```

   `gh` pide el valor por la terminal; pega el token del paso 1.4.

## 3. Deploy: aprobación y verificación

1. Cada merge a `main` corre el CI; si termina en verde y `DEPLOY_ENABLED=true`, se crea un
   run "Deploy <sha>" en Actions que espera tu aprobación. Para el primer deploy, vuelve a
   correr el CI de `main` como en 2.3.
2. Aprobar: Actions → el run "Deploy <sha>" → Review deployments → marca `production` →
   Approve and deploy. Antes de aprobar, revisa qué SHA es y qué PR lo trajo.
3. Lo que hace el job, en orden: verifica configuración, checkout del SHA exacto, lee el
   head de Alembic, instala la CLI de Heroku, anota la release actual, captura un backup
   (`heroku pg:backups:capture`), hace `git push` a `https://git.heroku.com/<app>.git`,
   espera la release (la release phase corre `python -m app.cli release`: migración e
   importación de contenido como borradores) y hace el smoke.
4. Verificación tras un deploy verde:

   ```bash
   heroku releases --app <app> -n 3
   heroku releases:output --app <app>
   curl -s https://<host>/health
   curl -s https://<host>/api/v1/ready
   ```

   Se ve la release nueva `succeeded`, la salida de la release phase con
   `INFO  [alembic…] Running upgrade …` (o nada si no había migraciones) y las líneas de
   importación; `/health` → `{"status":"ok"}`; `/ready` →
   `{"status":"ready","migration":"<head>"}` con el head que imprimió el job.
5. Solo después del **primer** deploy: dyno Basic (decisión de G0) y comprobación.

   ```bash
   heroku ps:type web=basic --app <app>
   heroku ps --app <app>
   ```

   Se ve `web.1: up` con tipo `Basic`.
6. Si el job falla después del push, el resumen del run imprime el comando de rollback
   exacto (sección 6).

## 4. Admin inicial (G1)

```bash
heroku run --app <app> -- python -m app.cli create-admin-invite --email <correo>
```

Imprime `Invitación (admin) para <correo>, vence …` y un enlace
`https://<host>/aceptar#t=…`. Ábrelo antes de que venza (72 h), elige la contraseña y
acepta el aviso. Las invitaciones de rol admin solo salen de la CLI. Si pierdes el acceso:

```bash
heroku run --app <app> -- python -m app.cli reset-link --email <correo>
```

## 5. Ensayo de restauración (NFR-09, antes de G4)

En una base desechable local (Docker), nunca sobre la de producción:

```bash
heroku pg:backups:capture --app <app>
heroku pg:backups:download --app <app> --output /tmp/pcre-ensayo.dump
docker run -d --name pcre-restore -e POSTGRES_PASSWORD=ensayo -p 55432:5432 postgres:16
sleep 5
docker exec -i pcre-restore pg_restore --no-owner --no-acl -U postgres -d postgres < /tmp/pcre-ensayo.dump
docker exec pcre-restore psql -U postgres -c "select version_num from alembic_version" \
  -c "select count(*) as usuarios from users" -c "select count(*) as revisiones from content_revisions"
cd apps/backend
DATABASE_URL=postgresql+psycopg://postgres:ensayo@localhost:55432/postgres uv run alembic current
cd ../..
docker rm -f pcre-restore && rm /tmp/pcre-ensayo.dump
```

Se ve el mismo `version_num` que `/api/v1/ready` en producción, los conteos que esperas y
`alembic current` con `(head)`. Anota fecha, id del backup y resultado en `STATE.md` (gate
G4). Si `pg_restore` muestra errores, no invites alumnos: es un hallazgo.

## 6. Rollback

- **Código** (lo más común, segundos):

  ```bash
  heroku releases --app <app> -n 5
  heroku rollback v<N> --app <app>
  curl -s https://<host>/health
  ```

  Regresa imagen y comando a la release `v<N>`. Las migraciones son *expand*, así que el
  código anterior funciona con el esquema nuevo. Si entre `v<N>` y la actual hubo una
  migración, `/api/v1/ready` responde 503 `migration_mismatch` hasta el siguiente deploy
  hacia adelante: es esperado (la base va adelante del código) y la app sigue sirviendo.
- **Contenido:** en `/admin/contenido`, retira la revisión publicada o vuelve a publicar la
  anterior. No hace falta deploy.
- **Datos** (último recurso; borra todo lo escrito después del backup):

  ```bash
  heroku maintenance:on --app <app>
  heroku pg:backups --app <app>
  heroku pg:backups:restore <id-del-backup> DATABASE_URL --app <app> --confirm <app>
  heroku maintenance:off --app <app>
  ```

## 7. Logs y errores

```bash
heroku logs --tail --app <app>
heroku logs -n 1500 --app <app> --source app | grep '<request_id>'
heroku logs -n 500 --app <app> --source heroku
```

- Los logs de la app son JSON de una línea, sin correos ni contenido de respuestas: cada
  petición trae `request_id`, ruta, estado, duración y `user_ref` (seudónimo con
  `LOG_SALT`). El alumno ve el mismo `request_id` en el mensaje de error.
- Heroku guarda pocas líneas: los 5xx quedan también en `/admin/piloto` → Errores (30 días).
- Los errores del router (`H12` timeout, `H10` caída, `R14` memoria) aparecen con
  `--source heroku`.

## 8. Run de audio (G2)

1. Environment `content-audio` con revisor obligatorio **antes** del secret (igual que 2.1,
   con `content-audio`), y después el secret `DEEPGRAM_API_KEY` del proyecto propio de PCRE:

   ```bash
   gh secret set DEEPGRAM_API_KEY --env content-audio --repo astraDukoWave/pcre-learning-platform
   ```

2. Costo estimado sin red (local):

   ```bash
   cd apps/backend
   uv run python ../../scripts/content/generate_audio.py --unit u1 --dry-run
   ```

   Imprime guiones, caracteres y costo estimado; sale con 2 si supera `--max-chars`.
3. Actions → "Audio de contenido (TTS)" → Run workflow → `unit` (`u1`, `inicial` o
   `final`) y `max_chars` → aprobar el environment. El run escribe el conteo en el resumen,
   genera los MP3 y abre un PR `content/audio-<unidad>-<run>`.
4. Escucha cada MP3 contra su guion y llena `reviewed_by` y `reviewed_at` en
   `content/toefl-ibt-2026-b1-b2/audio/manifest.yaml` con un commit en esa rama (ese push
   dispara el CI; un PR abierto por el bot no lo dispara solo). Mergea con CI verde. El
   siguiente deploy importa las revisiones nuevas como borradores.

## 9. Publicación de una unidad (G3)

1. Tras el deploy, `/admin/contenido` lista las revisiones en borrador de la unidad. Las que
   tienen audio pendiente o hallazgos materiales abiertos no se pueden aprobar.
2. Abre cada revisión, revisa el texto, las respuestas, las fuentes y el audio con el
   paquete de revisión (`docs/contenido/revision/u1.md`), y pulsa "Aprobar el hash …".
3. En la lista, "Publicar lo aprobado de la unidad". Verifica con una cuenta interna de
   alumno (marcada como interna en `/admin/usuarios`) que la ruta muestra la unidad.
4. Para retirar: botón "Retirar" en la revisión publicada (sección 6).

## 10. Invitaciones (G4)

Solo con el aviso de privacidad aprobado (G4), la restauración ensayada (sección 5) y el
dictamen de activación.

1. `/admin/usuarios` → "Correo" → "Crear invitación". El enlace se muestra **una sola
   vez**: cópialo y envíalo tú por un canal privado. Vence en 72 h.
2. Si vence o se pierde, crea otra invitación. Un reset de contraseña sale del mismo panel
   ("Enlace de reset", 24 h, un uso).
3. Marca como interna (casilla de la fila) toda cuenta de prueba tuya: el panel del piloto
   las excluye.

## 11. Primeros pasos ante un incidente

1. ¿Responde? `curl -s https://<host>/health` y `curl -s https://<host>/api/v1/ready`;
   `heroku ps --app <app>`; `heroku status`.
2. ¿Qué cambió? `heroku releases --app <app> -n 5`. Si empezó con el último deploy, rollback
   de código (sección 6) y después se investiga.
3. ¿Qué dice? `/admin/piloto` → Errores, y `heroku logs` con el `request_id` que reporte el
   alumno (sección 7).
4. ¿La base? `heroku pg:info --app <app>` y `heroku pg:diagnose --app <app>`.
5. Si hay riesgo para datos de alumnos: `heroku maintenance:on --app <app>`, "Cerrar
   sesiones" en `/admin/usuarios` si una cuenta está comprometida, y documenta qué datos y
   de quién.
6. Si se filtró un token: revócalo (`heroku authorizations:revoke <id>` o en el proveedor),
   crea uno nuevo y reemplaza el secret en GitHub (sección 2.4).
7. Anota el incidente y la causa en `STATE.md` (desviación) para la siguiente sesión.

## 12. Prueba manual en teléfonos (H-6, después de G1)

En un iPhone (Safari) y un Android (Chrome) actuales, con la URL de Heroku y una cuenta
interna de alumno. Marca cada casilla; si algo falla, captura de pantalla y el
`request_id` del mensaje.

- [ ] Aceptar una invitación: el correo aparece fijo, el aviso de privacidad se abre y se
  puede volver; la contraseña se escribe sin que el teclado tape el botón.
- [ ] Diagnóstico: empezar, responder dos preguntas, salir con «atrás» y retomar donde iba.
- [ ] Lectura (L1): elegir, enviar, ver el feedback y pedir una pista.
- [ ] Escucha (L2): el audio suena, se puede repetir y la transcripción aparece como ayuda.
- [ ] Escritura (L3): ordenar fichas tocándolas y escribir el correo; el contador de
  palabras se actualiza.
- [ ] Habla (L4): el navegador pide el micrófono, se graba, se reproduce lo grabado y nada
  se sube; con el permiso denegado aparece la explicación y «No pude grabar».
- [ ] Escenario: recorrer el diálogo hasta el final.
- [ ] Checkpoint: completarlo y ver los resultados por objetivo.
- [ ] Panel (con tu cuenta admin): `/admin/contenido`, `/admin/piloto` y
  `/admin/usuarios` se leen sin desplazamiento horizontal.

Anota el resultado (modelo, versión del sistema y del navegador) en `STATE.md`.

## 13. Smoke de rendimiento (NFR-03, local)

Contra el build de producción local, nunca contra Heroku (crea intentos con la cuenta que
usa). Desde `apps/backend`, con la base desechable `pcre_migcheck`:

```bash
export DATABASE_URL=postgresql+psycopg://pcre:pcre@localhost:5432/pcre_migcheck
uv run python ../../scripts/dev/dbtool.py reset
uv run python -m app.cli release
APP_ENV=dev uv run python -m app.cli dev-seed --student-email perf@example.com
(cd ../frontend && npm run build)
APP_ENV=prod APP_ORIGIN=http://localhost:8000 LOG_LEVEL=WARNING LOG_SALT=perf PORT=8000 \
  uv run sh -c "$(uv run python ../../scripts/ci/heroku_cmd.py web)" &
uv run python ../../scripts/perf/smoke.py --base-url http://localhost:8000 \
  --email perf@example.com --password practica-local-1
```

Imprime p50, p95 y máximo por endpoint y sale con 0 si todo p95 < 800 ms. El baseline está
en `docs/reviews/mvp-01-perf-smoke.md`.

## 14. IA y voz: benchmark (G5a) y activación (G5)

Tres capacidades con costo, todas apagadas por omisión y *fail-closed*: si falta la bandera,
el presupuesto, el precio o el proveedor, responden 503 `capability_disabled` y la interfaz
ofrece la alternativa sin costo (autoevaluación o práctica por texto).

| Capacidad | Bandera | Además necesita |
|---|---|---|
| Feedback con IA (escritura, entrevista y voz) | `AI_FEEDBACK_ENABLED` | `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_PRICE_INPUT_PER_MTOK_MICROUSD`, `GEMINI_PRICE_OUTPUT_PER_MTOK_MICROUSD` |
| Transcripción de grabaciones | `STT_ENABLED` | `DEEPGRAM_API_KEY` (precio por omisión: `STT_PRICE_PER_MIN_MICROUSD=4300`) |
| Coach de voz | `VOICE_ENABLED` | `DEEPGRAM_API_KEY`, `VOICE_MAX_MINUTES_PER_USER_MONTH` (precio por omisión: `VOICE_PRICE_PER_MIN_MICROUSD=75000`) |
| Las tres | — | `BUDGET_GLOBAL_MONTHLY_MICROUSD`, `BUDGET_USER_MONTHLY_MICROUSD` |

### 14.1 Benchmark del feedback (G5a, antes de G5)

1. Proyecto de Google **solo para PCRE** (no el de CareerAI), con facturación y una alerta de
   presupuesto: https://console.cloud.google.com/billing → Presupuestos y alertas → Crear,
   USD 25 al mes, alertas al 50, 80 y 100 %. La alerta avisa; el tope real lo pone la app.
   La facturación activa es obligatoria: en el nivel gratuito de la Gemini API, Google puede
   usar los datos para mejorar sus productos, y el aviso de privacidad dice que no.
2. Llave de la Gemini API de ese proyecto: https://aistudio.google.com/apikey → Crear llave en
   el proyecto de PCRE. No la pegues en ningún chat.
3. Environment `evals` con revisor obligatorio y su secret (repo → Settings → Environments →
   New environment `evals` → Required reviewers: tu usuario → Add environment secret
   `GEMINI_API_KEY`). Con `gh`:

   ```bash
   gh api -X PUT repos/astraDukoWave/pcre-learning-platform/environments/evals \
     -F "reviewers[][type]=User" -F "reviewers[][id]=$(gh api user --jq .id)"
   gh secret set GEMINI_API_KEY --env evals --repo astraDukoWave/pcre-learning-platform
   ```

4. Precio vigente de los modelos candidatos en https://ai.google.dev/gemini-api/docs/pricing
   (USD por millón de tokens de entrada y de salida).
5. Run (Actions → «Evaluación del feedback (modelos reales)» → Run workflow), por ejemplo:

   ```bash
   gh workflow run feedback-eval.yml --repo astraDukoWave/pcre-learning-platform \
     -f models="gemini-3.1-flash-lite=<entrada>/<salida>" -f max_cost_usd=2
   gh run watch --repo astraDukoWave/pcre-learning-platform
   ```

   Aprueba el despliegue al environment `evals` cuando GitHub lo pida. El run sube el
   reporte como artefacto y lo muestra en el resumen: debe decir qué modelo cumple la regla
   de selección (`evals/README.md`). Pásale al agente la URL del run para que commitee el
   reporte en `docs/reviews/mvp-02-feedback-eval.md`.

### 14.2 Deepgram (antes de G5)

1. Proyecto **propio de PCRE** en https://console.deepgram.com (no el de CareerAI).
2. Billing → saldo prepagado (sugerido: USD 10) y **Auto-reload apagado**. El saldo es el
   tope duro del proveedor: si se acaba, la voz y la transcripción fallan cerradas (503 o
   `provider_error`) y la app ofrece la alternativa.
3. Confirma en la configuración del proyecto o de la cuenta que **no** participa en el
   programa de mejora de modelos de Deepgram (Model Improvement Program o equivalente): el
   aviso de privacidad dice que el proveedor no usa los datos para entrenar.
4. API Keys → Create a New API Key, rol `Member`, sin vencimiento corto; cópiala directo al
   paso 14.3.
5. Confirma en https://developers.deepgram.com/docs/voice-agent-llm-models que el modelo de
   `VOICE_THINK_MODEL` (por omisión `gpt-4o-mini` de `open_ai`) sigue en el nivel estándar,
   y en https://deepgram.com/pricing que el Voice Agent estándar sigue en USD 0.075/min y
   Nova-3 pregrabado en USD 0.0043/min. Si cambió, ajusta `VOICE_PRICE_PER_MIN_MICROUSD` o
   `STT_PRICE_PER_MIN_MICROUSD` (micro-USD por minuto) en el paso siguiente.

### 14.3 Activación (G5)

Requisitos: G1 hecho, G5a con un modelo que cumple la regla, el aviso de privacidad vigente
menciona a Deepgram y Google (`apps/frontend/src/legal/privacidad.md`) y el dictamen
`docs/reviews/mvp-02-activacion-cto-review.md` firmado.

1. Presupuestos (valores firmados en G0) y llaves, sin encender nada todavía:

   ```bash
   heroku config:set --app <app> \
     BUDGET_GLOBAL_MONTHLY_MICROUSD=25000000 \
     BUDGET_USER_MONTHLY_MICROUSD=8000000 \
     VOICE_MAX_MINUTES_PER_USER_MONTH=60 \
     GEMINI_MODEL=<modelo elegido en G5a> \
     GEMINI_PRICE_INPUT_PER_MTOK_MICROUSD=<USD por millón de entrada × 1 000 000> \
     GEMINI_PRICE_OUTPUT_PER_MTOK_MICROUSD=<USD por millón de salida × 1 000 000>
   heroku config:set --app <app> GEMINI_API_KEY   # pide el valor sin dejarlo en el historial
   heroku config:set --app <app> DEEPGRAM_API_KEY
   ```

   Si tu versión de la CLI no pide el valor, usa el dashboard: Settings → Config Vars →
   Reveal → Add. Comprueba con `heroku config --app <app>` que las llaves aparecen (Heroku
   las muestra) y que no hay `FEEDBACK_PROVIDER`, `STT_PROVIDER`, `VOICE_PROVIDER` ni
   `VOICE_AGENT_URL` (los dobles no se permiten en producción: la app no arranca).
2. Enciende una capacidad a la vez, en este orden, y prueba con tu cuenta interna de alumno
   entre cada una:

   ```bash
   heroku config:set --app <app> AI_FEEDBACK_ENABLED=true
   heroku config:set --app <app> STT_ENABLED=true
   heroku config:set --app <app> VOICE_ENABLED=true
   ```

   Cada `config:set` reinicia la app (segundos). Después de cada una:
   `curl -s https://<host>/api/v1/capabilities` (con sesión, desde el navegador:
   `/api/v1/capabilities`) muestra la capacidad en `true`.
3. Pruebas mínimas: un correo de L3 con «Pedir feedback (IA)»; una grabación de L4 con
   «Transcribir»; una práctica de voz del escenario de U1 con la casilla de guardar marcada,
   de más de 30 s, hasta ver el feedback final. Luego H-9 (sección 15).
4. En `/admin/consumo` debe verse el gasto del mes por capacidad; en `/admin/piloto` →
   «Voz e IA», minutos, sesiones, motivos de cierre, llamadas y costo frente al tope.

### 14.4 Rollback (segundos, sin deploy)

- Apagar una capacidad: `heroku config:set --app <app> VOICE_ENABLED=false` (o
  `STT_ENABLED`, `AI_FEEDBACK_ENABLED`). La app se reinicia; una práctica de voz abierta se
  corta y su reserva se concilia con el barrido al arrancar. Las nuevas responden 503 y la
  interfaz ofrece la alternativa.
- Apagar todo el gasto de golpe: `heroku config:unset --app <app> BUDGET_GLOBAL_MONTHLY_MICROUSD`
  (sin presupuesto, las tres capacidades quedan apagadas).
- Llave filtrada: revócala en el proveedor (Deepgram → API Keys → Delete; Google → AI Studio
  → borrar la llave), crea otra y reemplázala con `heroku config:set`. Revisa el gasto del
  proveedor y `/admin/consumo`.

### 14.5 Señales

- Logs (`heroku logs --tail --app <app> | grep -E 'voice_|ai_run_finished|capability_disabled'`):
  `voice_session_started` (hash de la sesión, escenario, `user_ref`), `voice_session_ended`
  (motivo, duración, ayudas, turnos), `voice_provider_error` (código), `ai_run_finished`
  (propósito, modelo, estado, latencia, costo), `voice_turn_disputed`. Nunca llevan texto de
  la transcripción ni del feedback.
- `/admin/consumo`: reservado y gastado del mes, global y por alumno; aviso al 80 %. Una
  ejecución `unknown` cuenta como gastada (no se asume consumo cero).
- `/admin/piloto` → «Voz e IA»: minutos, sesiones, motivos de cierre (muchos
  `provider_error` = problema del proveedor; muchos `silence` = UX), turnos «Eso no fue lo
  que dije» (calidad del reconocimiento) y valoración de las prácticas.
- Saldo de Deepgram (Billing) y alertas de Google: si una alerta llega antes que el aviso
  del 80 % de la app, apaga la capacidad y avisa al agente (desviación en `STATE.md`).

## 15. Prueba manual de voz (H-9, después de G5)

En un iPhone (Safari) y un Android (Chrome) actuales, con la URL de Heroku y una cuenta
interna de alumno; cada caso con audífonos y sin ellos. Marca cada casilla; si algo falla,
captura, el `request_id` del mensaje (si lo hay) y la hora.

- [ ] Abrir el escenario de U1 → «Practicar este escenario por voz con el coach»: se ven la
  situación, la duración, el aviso de Deepgram y la casilla de guardar.
- [ ] «Empezar»: el navegador pide el micrófono; el coach saluda en voz alta en menos de 5 s.
- [ ] Conversación completa de más de 1 minuto: el coach responde en ≤ 2.5 s después de que
  callas (anota la latencia percibida: rápida, aceptable o lenta) y respeta el escenario.
- [ ] Interrumpir al coach hablando: se calla y te escucha.
- [ ] «Repetir», «Más despacio» y «Pista»: cada una hace lo que dice.
- [ ] Subtítulos en vivo encendidos y apagados.
- [ ] «Detener»: ves duración, ayudas, el feedback (con la casilla marcada) y la
  transcripción; «Eso no fue lo que dije» en un turno oculta su observación.
- [ ] Micrófono denegado: aparece la explicación y «Practicar este escenario por texto».
- [ ] Red cortada (modo avión) a mitad: la práctica termina con aviso y el panel muestra el
  cierre `disconnect`.
- [ ] Pasar a otra app o bloquear el teléfono: la práctica termina con aviso.
- [ ] Deadline: deja correr una práctica 5 minutos; a los 4:30 llega el aviso y a los 5:00
  termina sola.
- [ ] Sin la casilla de guardar: al terminar no hay transcripción ni feedback, solo duración
  y ayudas.

Al terminar, en `/admin/piloto` → «Voz e IA» deben aparecer los motivos de cierre de tus
pruebas (`user_stop`, `disconnect`, `deadline`, `logout` o `silence`). Anota el resultado
(modelo, sistema, navegador, latencia percibida y motivos de cierre) en `STATE.md`.
