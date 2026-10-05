# Spec: mvp-01-nucleo-piloto

spec_id: MVP-01-SPEC-01
Ciclo SDD MVP-01 · Lane: Standard. Las acciones de alto riesgo conservan
su propio gate (ver "Riesgo por acción").
Estado: **PENDIENTE DE APROBACIÓN** (gate G0,
`docs/reviews/g0-arranque-autonomo-cto-review.md`).
Base: `main` @ `133c5e3`. Arquitectura: `docs/arquitectura.md` v1.0.
Contenido: `docs/contenido/contrato-curricular.md` v1.0.
Discovery: contrato PCRE-MVP-20261005 y spec de producto v0.3; contexto
comercial en `strategy.md`. Los tres son privados (Proyecto "English
StartUp").
Skills aplicadas: `brainstorm` (los cinco campos ya estaban resueltos en el
discovery y se reutilizan), `design-spec` v0.2 y `system-design-spec` v0.2
(reglas 0–10).

---

## Idea clarificada

- **Problema:** una persona que se considera B1 y necesita B2 para trabajo
  o estudios no tiene una práctica corta y diaria que le diga qué falló,
  por qué y qué repasar, con tareas parecidas a las del examen que le
  piden. `[hipótesis]` a validar con los primeros clientes.
- **Usuario y momento:** adulto hispanohablante que practica desde el
  celular en sesiones de 10 a 20 minutos, y el responsable editorial que
  publica contenido y observa el piloto.
- **Definition of done:** el piloto técnico del spec de producto v0.3 §9.
  El alumno recibe acceso individual, completa actividades, ve feedback,
  vuelve otro día y recupera su historial. El responsable observa
  resultados y corrige contenido sin alterar la evidencia de los intentos.
- **Fuera de scope v1:** ver "NO incluye".
- **Conflictos con decisiones previas:** dos, que G0 pide ratificar. ADR-08
  usa tablas nuevas en lugar de reinterpretar `courses`/`classes`
  (contrato §7). Y el encargo se divide en tres ciclos en lugar de un solo
  alcance M2 (contrato §2), por la regla de un sprint por spec.

## Resumen general

Hoy el repo tiene un backend de solo lectura con un curso, una clase y tres
preguntas; un modelo `User` sin autenticación; ni frontend, ni pruebas, ni
CI `[verified-this-session: árbol de 133c5e3; 0 workflows por la API de
GitHub]`. Además:

- `GET …/classes/{slug}` convierte `Question.options` de texto a lista
  sobre el objeto del ORM durante la lectura.
- El orden de clases y preguntas no es determinista (relaciones sin
  `order_by`) y `(course_id, slug)` no es único.
- El seed hace un commit por objeto y se da por "sembrado" si existe un
  curso, aunque haya fallado a la mitad.
- El esquema del alumno expone `hint` y `explanation` junto con la
  pregunta, y la explicación delata la respuesta.
- Las dependencias están fijadas en versiones de 2023 e incluyen
  `python-jose` y `passlib`, que esta solución no usa.
- `validate-phase1-final.sh` usa Compose v1 y espera una migración que ya no
  es el head.
- La memoria del proyecto registra un "Auth Core (bcrypt + JWT)" de la fase
  1.5 que no existe en ninguna rama remota `[contradicted]`: solo existen
  el modelo y los esquemas de `45b56cc`.

Este ciclo convierte el repo en la plataforma del piloto:

- Un adulto invitado entra desde el celular, hace un diagnóstico corto y
  practica la Unidad 1 de la ruta `toefl-ibt-2026-b1-b2` (lectura, escucha,
  escritura, habla y un escenario guiado).
- Recibe corrección inmediata en lo cerrado y autoevaluación guiada en lo
  abierto, y ve su progreso y sus repasos del día siguiente.
- Deja su opinión sobre cada lección.
- Jonathan publica solo contenido revisado desde un panel editorial,
  observa el piloto en un panel propio y despliega a Heroku con un clic de
  aprobación.

El feedback abierto con IA y el coach de voz llegan en MVP-02; las unidades
2–8, en MVP-03.

## Objetivos del usuario

1. Como alumna B1, quiero entrar con mi cuenta desde el celular, hacer una
   práctica corta y volver otro día con mi avance y mis repasos listos.
2. Como alumna, quiero saber qué fallé, por qué y qué practicar después,
   sin promesas de puntuación.
3. Como responsable del producto, quiero publicar solo contenido revisado,
   ver cómo lo usan mis primeros clientes y recibir sus comentarios sin
   tocar la base de datos a mano.

## Alcance estricto v1

### Incluye

- **Fundación:** dependencias modernizadas con `uv`, ruff, mypy,
  import-linter, pytest contra PostgreSQL real, Alembic leyendo
  `DATABASE_URL`, hallazgos legados corregidos, arranque de la sesión cloud
  y `make verify`.
- **CI/CD:** CI en cada PR (backend, migraciones, frontend, contrato,
  contenido, E2E, imagen de producción) con `ci-gate` como check requerido;
  workflow de deploy a Heroku con aprobación del environment; workflow de
  audio TTS con aprobación. La activación real de ambos es [HUMANO].
- **Identidad:** invitaciones, login y logout, sesiones revocables, CSRF,
  perfil y meta, consentimiento y mayoría de edad, reset asistido,
  revocación, exportación y borrado de cuenta, límites de abuso.
- **Contenido y editorial:** contenido como código (esquema, lint,
  cobertura), importación idempotente de borradores, revisiones, fuentes y
  hallazgos, aprobación por hash, publicación y retiro, vista previa como
  alumno y reportes de contenido.
- **Práctica:** los seis formatos (`choice`, `word_completion`,
  `sentence_order`, `short_writing`, `recorded_speaking`,
  `guided_dialogue`), audio de escucha, ayudas registradas por el servidor,
  intentos idempotentes y revisión fijada por lección.
- **Comprobaciones:** diagnóstico inicial y checkpoint de U1, sin ayudas ni
  soluciones antes de enviar.
- **Progreso:** inicio con "continuar", métricas con denominadores, racha,
  repaso espaciado 1/3/7 y resultados.
- **Producto:** valoración por lección, comentario general, eventos,
  errores del servidor y panel del piloto.
- **Contenido U1:** 4 lecciones, escenario en modo texto, checkpoint,
  diagnóstico inicial y guiones de audio, en estado `ready-for-review`, con
  su paquete de revisión (`make review-packet UNIT=u1`).
- **Operación:** cabeceras de seguridad, logs sin datos personales,
  readiness, runbook (deploy, rollback, backup y restauración, admin,
  invitaciones, publicación), aviso de privacidad y términos en borrador,
  accesibilidad y smoke de rendimiento.
- **Diseño:** sistema de tokens y componentes según "Dirección visual".

### NO incluye

- Feedback con IA, transcripción y coach de voz (MVP-02).
- Unidades 2–8, formulario final y escenarios 2–8 (MVP-03).
- Pagos, registro abierto, envío de correos o mensajes, apps nativas,
  organizaciones o multi-institución.
- Otros exámenes o niveles, motor adaptativo, predicción de puntuación,
  certificados, rankings, avatares, conversación libre.
- SSR o Next.js, Redis, colas y workers, object storage, notificaciones
  push.
- Editor visual de contenido: el contenido se edita en archivos (ADR-03).
- Grabaciones guardadas en el servidor: en MVP-01 la grabación no sale del
  dispositivo.

## Calibración de escala (regla 0)

La de `docs/arquitectura.md` §2: valor actual 0; pico esperado de 20
cuentas, 10 peticiones concurrentes y 3 sesiones de voz en 4 semanas de
piloto `[supuesto]`. Este ciclo aplica lo que justifica el valor actual
(un dyno, PostgreSQL, sin caché ni colas) y deja los demás componentes como
triggers escritos en esa misma sección.

## Requisitos

### Funcionales

- **REQ-01 · Base reproducible.**
  - Python 3.12 con `uv` (`apps/backend/pyproject.toml` + `uv.lock`) y
    Node 22 con npm (`apps/frontend/package-lock.json`). Dependencias en
    versiones estables actuales; se retiran `python-jose`, `passlib`,
    `bcrypt` y `requirements.txt`.
  - `Makefile` en la raíz con `setup`, `db-up`, `db-reset`, `migrate`,
    `dev`, `test`, `lint`, `typecheck`, `content-lint`, `openapi`, `e2e` y
    `verify`. `make verify` corre lint, tipos, contratos de import, pruebas
    unitarias y de integración, chequeo de migraciones, lint de contenido,
    pruebas y build del frontend y drift del contrato. Tras `make setup`,
    no necesita red ni llaves.
  - `scripts/dev/cloud-session-start.sh` y su hook `SessionStart` en
    `.claude/settings.json`. Solo actúa si `CLAUDE_CODE_REMOTE=true`:
    arranca PostgreSQL, crea de forma idempotente el rol y las bases
    `pcre` y `pcre_test`, ejecuta `uv sync` y `npm ci` si cambió el
    lockfile, imprime un resumen y termina en menos de 10 minutos.
  - `docker-compose.yml` solo para desarrollo local o Codespaces: sintaxis
    de Compose v2 (sin `version`) y PostgreSQL 16.
  - Se eliminan `validate-phase1-final.sh` (lo reemplaza `make verify`) y
    los endpoints legados `/api/v1/courses*`. Las tablas legadas no se
    tocan (ADR-08). `docs/REQUIREMENTS.md` queda como histórico.
- **REQ-02 · CI.**
  - `.github/workflows/ci.yml` en `pull_request` y `push` a `main`, con
    `permissions: contents: read`, concurrencia por ref y sin secretos.
  - Jobs:
    - `backend`: ruff (check y format), mypy, `lint-imports` y pytest
      contra un servicio PostgreSQL 16.
    - `migrations`: base vacía → head; esquema legado en `816c80672425`
      con el seed legado → head; `alembic check`; downgrade y upgrade de
      cada migración nueva en una base desechable.
    - `frontend`: `npm ci`, typecheck, ESLint, Vitest y build.
    - `contract`: OpenAPI exportado igual a `docs/api/openapi.json` y tipos
      TypeScript regenerados sin diferencias.
    - `content`: lint de contenido y `docs/contenido/cobertura.md` sin
      diferencias al regenerarlo.
    - `e2e`: Playwright (Python) con Chromium contra el frontend compilado
      y servido por FastAPI, PostgreSQL de servicio y proveedores falsos;
      trazas y capturas como artefactos si falla.
    - `image`: build del `Dockerfile` raíz y arranque con el comando
      `run.web` leído de `heroku.yml`, junto a un contenedor PostgreSQL.
      Sondas: `/health`, `/api/v1/ready`, `/` (contiene el root de la
      SPA), `/api/v1/no-existe` (404 JSON). Más un grep del bundle buscando
      llaves y hosts de proveedores.
    - `workflows`: actionlint.
    - `ci-gate`: depende de todos los anteriores y es el único check
      requerido por el ruleset. Nunca se renombra ni se elimina.
  - Duración objetivo: 15 minutos o menos.
- **REQ-03 · Deploy aprobado.**
  - `heroku.yml`: `build.docker.web: Dockerfile`; `release` con `image:
    web` y `alembic upgrade head` seguido de la importación de contenido
    (solo borradores); `run.web` con el comando de `docs/arquitectura.md`
    §11.
  - `.github/workflows/deploy.yml`: se dispara tras un CI exitoso en
    `main`. El job `deploy` usa `environment: production` (revisor
    obligatorio, que configura Jonathan) y concurrencia `production` (una
    ejecución pendiente más nueva reemplaza a la anterior).
  - Activación explícita: el job solo corre si la variable del repo
    `DEPLOY_ENABLED` vale `true` (la define Jonathan en G1). Sin ella, el job
    se omite y el run no queda en verde. Con ella, pero sin el secret
    `HEROKU_API_KEY` o sin la variable `HEROKU_APP_NAME`, falla con el
    mensaje "deploy no configurado". Nunca termina en verde sin desplegar.
  - Pasos del job:
    - Checkout del SHA exacto con historia completa.
    - Instala la CLI de Heroku y captura un backup de la base.
    - Hace `git push` a `https://git.heroku.com/$HEROKU_APP_NAME.git`
      (`HEAD:main`) y espera la release.
    - Smoke: `/health`, `/api/v1/ready` con la migración head esperada y
      `/`. Si algo falla, el job falla e imprime el comando exacto de
      rollback.
- **REQ-04 · Invitación y acceso.**
  - Un admin crea una invitación (email, rol `student`). El enlace dura
    72 h (configurable), se muestra una sola vez para copiarlo y no se
    envía por correo. Las invitaciones de rol `admin` solo salen de la CLI.
  - Aceptar: el email viene de la invitación y no se edita. El alumno
    escribe su contraseña (10–128 caracteres) y su confirmación, acepta el
    aviso de privacidad (se muestra su versión), confirma que es mayor de
    edad y, si quiere, pone un nombre. Se crean el usuario y la sesión y se
    abre el onboarding.
  - Login con email y contraseña, error genérico, límite de intentos,
    rotación de sesión; cookie y token CSRF en la respuesta. Logout revoca
    la sesión actual. Vencimiento: 7 días absoluto y 24 h de inactividad.
  - Admin: lista de usuarios (email, alta, último acceso, marca interna,
    resumen de progreso), enlace de reset (24 h, un uso), revocar sesiones
    y marcar como interno.
  - Confirmar un reset: contraseña nueva → se revocan todas las sesiones →
    sesión nueva.
- **REQ-05 · Perfil y meta.**
  - Onboarding: propósito (trabajo, estudios, certificación, otro, no lo
    sé); examen objetivo (TOEFL iBT, IELTS Academic, Cambridge B2 First,
    TOEFL ITP, otro con texto, no lo sé); puntuación y fecha objetivo
    opcionales; nivel percibido (A2, B1, B2, no lo sé) presentado como "tu
    percepción"; zona horaria detectada del navegador y editable.
  - Todo se edita después en "Perfil". El alumno no puede cambiar su rol
    ni su email.
  - "Tu meta" nunca se presenta como nivel acreditado.
- **REQ-06 · Control de los datos del alumno.**
  - "Descargar mis datos": un JSON con perfil, intentos (respuestas y
    resultados), comprobaciones, repasos, feedback y reportes, sin datos de
    otras personas.
  - "Borrar mi cuenta": se confirma escribiendo la contraseña. Borra al
    usuario y, en cascada, sesiones, intentos, ayudas, corridas, repasos,
    progreso, feedback, reportes, eventos e idempotencia; luego cierra la
    sesión. El email puede invitarse de nuevo.
  - La app no envía mensajes automáticos.
- **REQ-07 · Contenido como código.**
  - Esquema ejecutable del contrato curricular §9 (Pydantic), carga de
    YAML y hash sha256 del JSON canónico.
  - Lint con estas reglas:
    - Errores: esquema; claves únicas en toda la ruta; referencias
      existentes (objetivos, fuentes, rúbricas, audio); pools disjuntos
      (una clave de `assessment` nunca aparece en `practice` ni `review`);
      mínimos del contrato §5; marcadores prohibidos; apoyo en español solo
      en práctica de U1–U4.
    - Advertencias: reglas absolutas; extensiones fuera de rango; escucha
      sin audio revisado (`pending-audio`, que bloquea aprobar y publicar).
  - `make content-lint` regenera `docs/contenido/cobertura.md` (contrato
    §10).
  - `python -m app.cli content import --dir <ruta>`: valida todo antes de
    escribir; una sola transacción; upsert de ruta, unidades e ítems;
    revisión `draft` nueva solo si cambió el hash; nunca aprueba ni
    publica; imprime un resumen y termina con error si el lint falla.
  - La lección legada se exporta a `content/_legacy/` (contrato §14).
- **REQ-08 · Flujo editorial.**
  - Estados y reglas de `docs/arquitectura.md` §5.1 y del contrato §12.
  - Panel admin:
    - Lista de revisiones con filtros por tipo, estado y unidad.
    - Detalle con vista previa como alumno (modo práctica y modo
      comprobación) y vista de autor (claves, explicaciones, rúbricas).
    - Advertencias del lint, fuentes con afirmación y alcance, hallazgos
      (crear y resolver) y bitácora de decisiones.
  - Aprobar muestra el hash. Exige cero hallazgos materiales abiertos, cero
    errores de lint y audio revisado en escucha.
  - Publicar es atómico: la revisión publicada anterior pasa a
    `superseded`. Se puede publicar en lote todo lo aprobado de una unidad.
  - Retirar pide un motivo, bloquea intentos nuevos, conserva el historial
    y libera el progreso fijado.
  - Ningún camino de código permite que un modelo apruebe o publique.
- **REQ-09 · Recorrido.**
  - **Inicio:** acción principal "Continuar" (lección en curso → repaso
    vencido → siguiente lección recomendada), repasos pendientes, la meta
    y la invitación al diagnóstico si falta.
  - **Ruta:** unidades con sus lecciones publicadas, estado por lección
    (no iniciada, en curso, completada), escenario y checkpoint. Orden
    recomendado sin bloqueos.
  - No se muestran otros exámenes ni tarjetas vacías.
  - Una lección se retoma en la primera actividad sin responder.
- **REQ-10 · Motor de actividades.** Comportamiento en MVP-01:
  - `choice`: radios (una respuesta) o casillas (varias), operable con
    teclado; al enviar, resultado y explicación.
  - `word_completion`: campos en línea con el inicio visible; resultado
    por hueco; variantes aceptadas; sin distinguir mayúsculas por defecto.
  - `sentence_order`: fichas que se tocan para armar la oración, con
    alternativa de teclado (seleccionar y mover). Se compara con los
    órdenes aceptados y, al enviar, se muestra uno correcto.
  - `short_writing`: área de texto con contador de palabras; al enviar,
    autoevaluación con la rúbrica (0–3 por criterio) y después el ejemplo
    comentado. Se puede reformular: un intento nuevo que referencia al
    anterior.
  - `recorded_speaking`: graba con MediaRecorder hasta `response_seconds`,
    reproduce localmente, ofrece el audio modelo y la autoevaluación. Nada
    se sube; la interfaz lo dice ("Tu grabación no sale de tu
    dispositivo"). Camino claro si el micrófono se deniega.
  - `guided_dialogue`: secuencia tipo conversación con opciones por turno,
    retroalimentación por opción y resumen al terminar.
  - Común: ayudas servidas por el servidor (REQ-11); contador de
    reproducciones del audio; errores de validación claros. El resultado
    nunca se muestra antes de que el servidor confirme.
- **REQ-11 · Intentos y ayudas.**
  - `POST /api/v1/attempts` con `Idempotency-Key`. El servidor:
    - Comprueba que la actividad pertenece a una revisión accesible para
      el alumno (publicada o fijada) y valida la forma de la respuesta.
    - Corrige de forma determinista `choice`, `word_completion`,
      `sentence_order` y `guided_dialogue`, y guarda la autoevaluación de
      `short_writing` y `recorded_speaking`.
    - Registra las ayudas servidas desde el intento anterior y actualiza
      progreso y repasos en la misma transacción.
  - **Las ayudas las sirve el servidor.** Pistas, apoyo en español,
    transcripción y ejemplo no viajan en el DTO de la lección: se piden a
    `POST /api/v1/aids` (`activity_id`, `kind`, `index`), que las devuelve
    y deja registro en `served_aids`. En modo comprobación responde 403.
    Las reproducciones de audio se registran como dato reportado por el
    cliente.
  - Una lección está completa cuando todas sus actividades del pool
    `practice` se enviaron al menos una vez. Completar no significa
    acertar.
  - El DTO de la lección incluye el último intento del alumno por
    actividad (respuesta y resultado) para retomarla.
  - Revisión fijada: un alumno que empezó una lección sigue en esa
    revisión hasta completarla (EDGE-04, EDGE-05).
- **REQ-12 · Comprobaciones.**
  - **Diagnóstico inicial** de ruta: una corrida por alumno; un admin
    puede reiniciarlo. **Checkpoint de U1:** se puede repetir; las corridas
    se numeran y la primera es la comparable.
  - Iniciar crea una corrida con orden fijado. El DTO va sin pistas,
    apoyos, transcripciones ni soluciones. Cada respuesta se guarda al
    momento (`PUT`) sin feedback.
  - Enviar (idempotente) corrige lo cerrado y muestra resultados por
    objetivo (aciertos sobre total), las explicaciones y los ejemplos de
    las producciones. Las producciones quedan "no evaluadas
    automáticamente" en MVP-01, con autoevaluación opcional.
  - Los ítems de comprobación vienen del pool `assessment` y nunca
    aparecen en práctica ni repaso (el lint lo garantiza).
  - Etiqueta visible: "Comprobación formativa: no es un examen oficial".
- **REQ-13 · Progreso y métricas.** Definiciones (contrato
  PCRE-MVP-20261005 §10):
  - **Avance:** lecciones completadas / lecciones publicadas de la versión
    de ruta inscrita ("2 de 4 lecciones de la Unidad 1"; nunca "% de
    inglés").
  - **Acierto inicial:** primer intento evaluable por actividad corregida
    automáticamente; numerador y denominador visibles, con periodo.
  - **Ayudas:** conteo por tipo; un resultado con ayuda se marca como tal.
  - **Objetivos a reforzar:** objetivos con primer intento fallido o
    repaso fallido en los últimos 30 días, con enlace a la evidencia y una
    siguiente acción.
  - **Revisión diferida:** desempeño sin ayudas en actividades del pool
    `review`, separado de la práctica.
  - **Producción:** promedios de autoevaluación con la etiqueta
    "autoevaluación".
  - **Racha:** días locales consecutivos con al menos un envío válido;
    varios envíos el mismo día cuentan una vez.
  - Con denominador cero se muestra "aún sin medición". Las cuentas
    internas quedan fuera de las métricas del piloto, no de su propio
    panel.
- **REQ-14 · Repaso espaciado.**
  - Un objetivo fallado (primer intento o repaso) pasa a etapa 0, vence a
    las 24 h y ofrece una reparación inmediata opcional (explicación y un
    ítem de repaso).
  - Un acierto sin ayudas en un repaso vencido avanza a la etapa 1 (+3
    días) y a la 2 (+7 días); después se queda en 7 días. Un fallo
    reinicia. Un acierto con ayudas no avanza.
  - El repaso elige una actividad del pool `review` del objetivo que el
    alumno no haya respondido. Si no queda ninguna, reutiliza la menos
    reciente marcada `repeated=true`, que no cuenta como recuperación
    diferida.
  - Intervalos configurables (`REVIEW_INTERVALS_HOURS=24,72,168`). Se
    actualizan en la transacción del intento. Los vencidos se calculan al
    pedirlos: sin cron.
- **REQ-15 · Feedback del producto y panel del piloto.**
  - Al terminar una lección o un escenario: "¿Qué tan útil fue esta
    lección?" de 1 a 5, con comentario opcional (≤ 1 000 caracteres) y
    botón para omitir.
  - "Enviar comentario", siempre disponible en el menú, con la página como
    contexto.
  - "Reportar un problema" en cada actividad, con categoría.
  - Panel del piloto (7 y 28 días): alumnos activos por día (sin cuentas
    internas), intentos, lecciones completadas, repasos hechos y
    vencidos, diagnósticos, valoración media, últimos comentarios, reportes
    abiertos y errores del servidor.
- **REQ-16 · Eventos de producto.** Lista cerrada: `invitation_accepted`,
  `login`, `diagnostic_started`, `diagnostic_completed`, `lesson_started`,
  `lesson_completed`, `attempt_submitted`, `aid_used`, `feedback_viewed`,
  `review_completed`, `checkpoint_completed`, `content_reported`,
  `feedback_submitted`. Solo ids y enumerados; se guardan en
  `product_events`; sin analítica de terceros.
- **REQ-17 · Páginas legales y de ayuda.**
  - `/privacidad`: responsable, datos que se recogen, finalidades,
    encargados y transferencias (Heroku en EE. UU.; desde MVP-02, Deepgram
    y Google), cómo ejercer acceso, rectificación, cancelación y oposición
    (exportar y borrar en la app, más el contacto de
    `PRIVACY_CONTACT_EMAIL`) y cómo se comunican los cambios.
  - `/terminos`: producto formativo, sin garantías, uso aceptable.
  - `/como-funciona`: método, comprobaciones formativas, aviso de marca de
    ETS y qué se guarda.
  - El agente redacta los textos y los marca como borrador en el repo.
    `CONSENT_VERSION` identifica la versión aceptada. Invitar a personas
    reales exige que Jonathan apruebe el texto (gate G4).
- **REQ-18 · Dirección visual y accesibilidad:** la sección siguiente.

### No funcionales

- **NFR-01 · Aislamiento.** Cero lecturas o escrituras cruzadas: un test
  negativo con dos cuentas por cada endpoint con datos de alumno (404).
- **NFR-02 · Persistencia.** Reiniciar el servidor no pierde intentos
  confirmados ni publicaciones (el E2E reinicia el proceso).
- **NFR-03 · Rendimiento.** p95 < 800 ms con 10 peticiones concurrentes en
  `GET /me`, `GET /learning-paths/{id}`, `GET /lessons/{id}`, `POST
  /attempts` y `GET /me/progress`. Se mide con `scripts/perf/smoke.py`
  contra el build de producción local y se registra el resultado. No es un
  gate de CI: si no se cumple, se registra una desviación.
- **NFR-04 · Resiliencia.** Nunca "Guardado" sin un 2xx. Aviso de
  conexión perdida. Solo se reintenta lo idempotente. Cada error dice qué
  pasó y qué hacer.
- **NFR-05 · Seguridad.** `docs/arquitectura.md` §7 (sesiones, CSRF,
  Origin, cabeceras, CSP, límites, Markdown sin HTML) con pruebas.
- **NFR-06 · Costo.** Ninguna llamada de pago en CI ni en desarrollo: las
  pruebas fallan si intentan abrir un socket hacia un host de proveedor. El
  TTS solo corre en su workflow aprobado y con tope.
- **NFR-07 · Observabilidad.** Logs JSON sin datos personales (un test
  verifica que no aparecen campos prohibidos), `X-Request-ID` en cada
  respuesta y `error_events`.
- **NFR-08 · Accesibilidad.** WCAG 2.2 AA en los flujos principales: axe en
  el E2E sin violaciones graves ni críticas, un recorrido completo solo con
  teclado y `prefers-reduced-motion` respetado.
- **NFR-09 · Recuperación.** Ensayo de backup y restauración documentado;
  Jonathan lo ejecuta antes de invitar alumnos (G4).
- **NFR-10 · Compatibilidad.** Navegadores de `docs/arquitectura.md` §10.
  El E2E corre también con viewport de teléfono (390 × 844). En iPhone y
  Android reales se prueba a mano [HUMANO].
- **NFR-11 · Plataforma.** Ninguna petición pasa de 25 s; nada se escribe
  fuera de `/tmp`; ante SIGTERM la app termina las peticiones en curso.
- **NFR-12 · Límites de arquitectura.** Contratos de import-linter de
  `docs/arquitectura.md` §4, con su prueba de falla.
- **NFR-13 · Contrato API.** Snapshot de OpenAPI y tipos generados sin
  diferencias.
- **NFR-14 · Calidad de contenido.** Lint y cobertura como checks de CI;
  ningún marcador pendiente en contenido `ready-for-review`.

## Dirección visual

Diseño para un producto educativo de adultos que estudian después del
trabajo, casi siempre en el teléfono. Su trabajo principal: dejar claro
qué hacer ahora y mostrar la corrección sobre las propias palabras del
alumno. Si la sesión tiene la skill `frontend-design`, se carga antes de
construir la interfaz.

**Concepto: el cuaderno corregido.** La hoja de práctica toma del cuaderno
escolar mexicano su cuadrícula tenue y su bolígrafo azul. La única pieza
llamativa es la corrección: el fragmento exacto que escribió o eligió el
alumno se resalta con marcatextos y la observación aparece como nota al
margen. Todo lo demás es sobrio.

**Paleta** (variables CSS en `tokens.css`):

| Token | Hex | Uso |
|---|---|---|
| `--paper` | `#F6F8FB` | Fondo: papel frío, no crema |
| `--ink` | `#16233F` | Texto principal |
| `--pen` | `#2347C6` | Acción principal, enlaces y foco |
| `--grid` | `#D9E1EC` | Cuadrícula, reglas y bordes |
| `--marker` | `#E8F25B` | Solo para resaltar el patrón o la evidencia, siempre con texto `--ink` encima |
| `--note` | `#6B3FB5` | Notas al margen: feedback y "revisa esto" |
| `--ok` | `#1F7A55` | Acierto |
| `--system-error` | `#B42318` | Solo errores del sistema (red, validación), nunca los errores de aprendizaje |

Los errores de aprendizaje no usan rojo: usan `--note`, un ícono y texto
("Revisa esto"). Cada combinación de texto y fondo cumple AA. En MVP-01
solo hay tema claro; los tokens permiten agregar el oscuro después.

**Tipografía** (archivos servidos desde la app, licencia OFL):

- **Atkinson Hyperlegible Next** para la interfaz en español: diseñada
  para legibilidad, encaja con un producto de aprendizaje.
- **Literata** para el material en inglés (textos, opciones, ejemplos): el
  cambio de tipografía le dice al alumno "esto es el idioma que
  practicas". Interlineado de 1.6 en Literata y 1.5 en la sans; líneas de
  70 caracteres o menos.
- Escala con razón 1.25 sobre una base de 17 px en teléfono y 18 px en
  escritorio.

**Composición:**

- Teléfono: una columna, la hoja de la actividad y una barra inferior fija
  con una sola acción principal por estado ("Enviar respuesta",
  "Siguiente actividad").
- Escritorio, en lectura y escucha: estímulo a la izquierda, preguntas a la
  derecha y notas al margen junto a la respuesta.
- Listas con reglas finas en lugar de tarjetas idénticas. Inicio con una
  sola acción grande ("Continuar") y lo demás en lista. La racha nunca pesa
  más que la siguiente actividad.

**Movimiento:** un único momento: al llegar el feedback, el marcatextos
recorre el fragmento de evidencia (250 ms). Con movimiento reducido,
aparece sin animación.

**Textos de la interfaz:** tú, verbos simples, frases en caso normal (sin
mayúsculas sostenidas), sin flechas en los botones y sin etiquetas
decorativas sobre los títulos. Un error dice qué pasó y cómo seguir, sin
disculpas. Una pantalla vacía invita a actuar ("Aún no tienes repasos.
Termina una lección para empezar.").

**Pantallas:** acceso e invitación · onboarding · inicio · ruta · lección
(estímulo, respuesta, ayudas, feedback, siguiente) · comprobación (con
"Ayudas desactivadas" visible y envío confirmado) · resultados · perfil y
datos · páginas legales · admin: usuarios, contenido (lista, detalle,
vista previa), reportes y piloto. Estados de carga, vacío, error de red,
sesión vencida y micrófono denegado en cada una.

## Comportamiento esperado

### Flujo feliz

1. Jonathan crea una invitación en el panel, copia el enlace y se lo manda
   a la alumna por WhatsApp.
2. Ella lo abre en el celular, crea su contraseña, lee y acepta el aviso
   de privacidad, confirma que es mayor de edad y elige su meta (o "no lo
   sé").
3. En "Inicio" ve "Empieza con tu diagnóstico (unos 20 minutos)". Lo hace
   sin ayudas y ve resultados por objetivo, sin ninguna afirmación de
   nivel.
4. Abre la lección 1 de la Unidad 1. Lee, responde, pide una pista, falla
   un ítem, ve la nota al margen sobre su respuesta y acierta el siguiente.
5. Cierra el navegador. Al volver, la lección retoma donde quedó, con sus
   respuestas.
6. Al día siguiente, "Inicio" muestra "2 repasos pendientes". Los hace con
   ítems nuevos del mismo objetivo y su racha sube a 2 días.
7. Termina la lección, la valora con 4 y deja un comentario.
8. Jonathan ve en el panel del piloto la actividad, la valoración y el
   comentario.

Flujo editorial: la release phase importa el contenido como borrador →
Jonathan abre la revisión, la ve como alumno, revisa claves y fuentes,
registra y resuelve hallazgos → aprueba (hash) → publica la unidad → las
alumnas la ven.

### Casos edge

- **EDGE-01 · Invitación vencida o ya usada.** Mensaje claro: "Este enlace
  ya no sirve. Pide uno nuevo a quien te invitó."
- **EDGE-02 · Doble envío o red intermitente.** La idempotencia devuelve
  el mismo resultado; nunca hay dos intentos y nunca se muestra
  "Guardado" sin confirmación.
- **EDGE-03 · Sesión vencida a mitad de una lección.** El borrador de la
  respuesta se conserva en el navegador; tras volver a entrar se restaura
  y se envía con la misma clave de idempotencia.
- **EDGE-04 · Se publica una revisión nueva mientras alguien está a mitad
  de la lección.** Esa persona termina con la revisión fijada; quien
  empieza después recibe la nueva.
- **EDGE-05 · Se retira una revisión a mitad de la lección.** Aviso
  ("Esta lección se retiró para corregirla"), la lección desaparece de la
  ruta y los intentos se conservan.
- **EDGE-06 · Recurso de otra cuenta.** 404, sin revelar si existe.
- **EDGE-07 · El audio no carga.** Botón para reintentar. En práctica, tras
  dos fallas se ofrece la transcripción como ayuda registrada. En
  comprobación el ítem queda "no evaluable (audio)", no como error.
- **EDGE-08 · Micrófono denegado.** Se explica cómo habilitarlo en el
  navegador; se puede continuar con "No pude grabar", que no se evalúa.
- **EDGE-09 · Diagnóstico repetido.** No se permite una segunda corrida
  salvo que un admin lo reinicie; el checkpoint sí se repite y su resultado
  muestra el número de corrida.
- **EDGE-10 · Cambio de zona horaria.** Los días ya registrados no cambian;
  los nuevos usan la zona nueva.
- **EDGE-11 · Contenido inválido.** El lint falla en la CI, así que nunca
  llega a `main`. Si la importación falla en la release phase (por
  ejemplo, base de datos), Heroku no promueve la release y la anterior
  sigue viva.
- **EDGE-12 · Reinicio del dyno durante una petición.** El cliente
  reintenta con la misma clave de idempotencia.
- **EDGE-13 · Aprobar o publicar con hallazgos materiales abiertos, errores
  de lint, audio sin revisar o un hash distinto.** 409 con el motivo.
- **EDGE-14 · Cuenta borrada.** Sesiones revocadas y datos eliminados; el
  email puede invitarse de nuevo.
- **EDGE-15 · Cuenta interna.** Su actividad no entra a las métricas del
  piloto.
- **EDGE-16 · Demasiados intentos de login.** 429 con `Retry-After` y un
  mensaje genérico.
- **EDGE-17 · Navegación atrás durante una comprobación.** La corrida
  persiste con sus respuestas guardadas y se retoma.

## Manejo de errores

| Situación | Qué ve el usuario | Qué se registra |
|---|---|---|
| Sin conexión o servidor caído al enviar | "No pudimos guardar tu respuesta. La conservamos aquí; vuelve a intentarlo." | Nada en el servidor; reintento con la misma clave |
| Sesión vencida | Pantalla de acceso; tras entrar, vuelve a donde estaba | info `session_expired` |
| Validación (422) | El campo y cómo corregirlo | info con `error_code` |
| Recurso ajeno o inexistente (404) | "No encontramos esto." + ir a Inicio | info |
| Rol insuficiente (403) | "Esta sección es para el equipo editorial." | warning con ruta |
| CSRF u Origin inválido (403) | "Recarga la página para continuar." | warning con origen |
| Conflicto editorial (409) | El motivo exacto (hallazgo abierto, hash distinto, audio sin revisar) | info |
| Límite de intentos (429) | "Espera un momento antes de intentarlo de nuevo." | warning con `user_ref` |
| Excepción inesperada (500) | "Algo falló de nuestro lado. Ya quedó registrado." + `request_id` | error con traza en logs y fila en `error_events` |

## Supuestos y decisiones abiertas

- `[supuesto]` Los primeros usuarios son adultos y el piloto excluye
  menores. Dueño: Jonathan.
- `[hipótesis]` La ruta tipo TOEFL iBT encaja con la meta de los primeros
  clientes. Dueño: Jonathan, pregunta 2 de G0. No bloquea MVP-01: la U1
  trabaja habilidades transversales.
- `[supuesto]` Jonathan revisa una unidad (4 lecciones, escenario y
  checkpoint) en 2 horas o menos. Se mide (ver Métricas).
- `[supuesto]` El piloto corre en un dyno Basic (sin sueño). Decide
  Jonathan en G1 por costo.
- `[supuesto]` El aviso de privacidad y los términos son borradores del
  agente; Jonathan los revisa antes de invitar (G4). No es asesoría legal.
- **Decisión abierta:** contenido y claves de respuesta en el repo público
  durante el piloto. Trigger en `docs/arquitectura.md` §2. Dueño: Jonathan.
- **Decisión abierta:** nombre comercial. "PCRE" choca en buscadores con
  la librería de expresiones regulares del mismo nombre; `APP_NAME` lo
  deja configurable (LB-05). Dueño: Jonathan.
- `[supuesto técnico]` MediaRecorder funciona en Safari iOS y Chrome
  Android actuales. Lo valida la prueba manual H-6.
- **Ratificación pedida en G0:** ADR-08 y la división en tres ciclos
  (ver "Idea clarificada").

## Riesgo por acción

| Acción propuesta | Clase | Gate que la cubre |
|---|---|---|
| Escribir código, pruebas, contenido borrador y docs en ramas con PR | Rutina | `ci-gate` |
| Mergear a `main` un PR con CI verde | Alto (permiso amplio a un agente) | G0: delegación firmada + ruleset de `main` |
| Crear workflows de deploy y audio sin secretos | Rutina | PR + actionlint |
| Configurar ruleset y environments del repo | Alto (permisos) | [HUMANO] Jonathan |
| Crear la app de Heroku, Postgres, config vars y `HEROKU_API_KEY` | Alto (secretos y dinero) | [HUMANO] Jonathan con el runbook |
| Desplegar a Heroku (primer deploy y siguientes) | Alto (producción) | G1: aprobación del environment `production` + dictamen de activación |
| Migrar una base con datos reales | Alto (datos) | G1: backup automático previo + migraciones expand + ensayo de restauración |
| Generar audio con TTS | Alto (dinero, acotado) | G2: aprobación del environment `content-audio` + tope de caracteres |
| Publicar contenido de U1 | Alto (impacto educativo) | G3: aprobación editorial de Jonathan en el panel |
| Invitar alumnos reales y guardar sus respuestas | Alto (datos personales) | G4: aviso aprobado + restauración probada + dictamen |
| Borrado de cuenta por el alumno | Alto (destructivo) | Confirmación con contraseña + pruebas |

## Release, rollback y evidencia

- **Ramas y PRs:** una rama por change set (o por grupo, si el plan lo
  dice), PR a `main` con `ci-gate` en verde y merge commit, nunca squash
  (conserva los SHAs que citan los planes).
- **Evidencia:** pruebas unitarias y de integración contra PostgreSQL,
  E2E en Chromium (escritorio y teléfono) con proveedores falsos, arranque
  de la imagen de producción, smoke de rendimiento y reporte de `verify`
  con evidencia por AC.
- **Deploy:** solo por `deploy.yml` tras la aprobación de Jonathan (G1).
- **Rollback:** `heroku rollback -a <app>` (código y comando de arranque);
  las migraciones expand mantienen compatible el esquema. Contenido:
  retirar la revisión o republicar la anterior desde el panel. Datos:
  `heroku pg:backups:restore` desde el backup previo al deploy, con el
  procedimiento del runbook.

## Métricas de resultado

| Métrica | Fuente | Baseline | Review | Decisión |
|---|---|---|---|---|
| Activación: invitados que completan el diagnóstico y una lección en 7 días | `product_events` | n/a | Semana 2 del piloto | Al menos 2 de 3 → continuar; si no, entrevista y revisión del onboarding |
| Uso recurrente: días activos por semana por alumno | `attempts.local_day` | n/a | Semanas 2 y 4 | ≥ 2 días por semana → continuar; < 1 → revisar duración de las sesiones |
| Completitud de U1 | `lesson_progress` | 0 de 4 | Semana 2 | Informativa |
| Utilidad percibida | `user_feedback` | n/a | Semanas 2 y 4 | Media ≥ 4 → continuar; < 3 → revisar contenido antes de U2 |
| Calidad del contenido: reportes por 100 intentos y hallazgos materiales abiertos | `content_reports`, `review_findings` | n/a | Semana 2 | > 2 por 100 intentos → revisar el lote antes de MVP-03 |
| Fiabilidad: envíos fallidos y errores 5xx por día | `error_events` | n/a | Semana 1 | > 1 % de envíos fallidos → corregir antes de seguir |
| Tiempo editorial por unidad | Nota en la decisión de aprobación | n/a | Tras publicar U1 | > 2 h → priorizar la revisión asistida (LB-04) |
| Evidencia formativa: diagnóstico vs. checkpoint en objetivos de U1 | `assessment_runs` | Diagnóstico | Tras el checkpoint | Solo descriptiva; sin inferencias causales con 2 o 3 personas |

La instrumentación de estas métricas son change sets del plan, no notas.

## Trazabilidad con PCRE-MVP-20261005

| Contrato | Aquí |
|---|---|
| RQ-01 Acceso por invitación | REQ-04 |
| RQ-02 Perfil y objetivo | REQ-05 |
| RQ-03 Recorrido | REQ-09 |
| RQ-04 Motor de actividades | REQ-10 |
| RQ-05 Intentos y feedback | REQ-11 (feedback abierto: MVP-02) |
| RQ-06 Comprobaciones | REQ-12 (formulario final: MVP-03) |
| RQ-07 Progreso y repaso | REQ-13, REQ-14 |
| RQ-08 Voz guiada | MVP-02 |
| RQ-09 Contenido editorial | REQ-07, REQ-08 |
| RQ-10 Recuperación y control | REQ-04, REQ-06, REQ-15 |
| RQ-11 Ruta completa | MVP-03 |
| NF-01 a NF-09 | NFR-01, NFR-02, NFR-03, NFR-04, NFR-05, NFR-06, NFR-07, NFR-08, NFR-09 |
| T01–T05, T07, T10 parcial y T12 parcial | MVP-01-PLAN-01 |
| T08, T09 | MVP-02 |
| T11 | MVP-03 |

## Archivos afectados (estimación, no contrato)

- **Raíz:** `Makefile`, `Dockerfile`, `heroku.yml`, `docker-compose.yml`,
  `.github/workflows/{ci,deploy,content-audio}.yml`, `.claude/settings.json`,
  `scripts/dev/`, `scripts/perf/`, `scripts/content/`, `AGENTS.md`,
  `CLAUDE.md`, `HANDOFF.md`, `STATE.md`, `README.md`.
- **Backend:** `apps/backend/pyproject.toml`, `uv.lock`, `.importlinter`,
  `alembic/` (migraciones nuevas), `app/{core,db,http}/`,
  `app/modules/{identity,content,practice,progress,insights}/`,
  `app/bootstrap.py`, `app/main.py`, `app/cli.py`, `tests/`; se eliminan
  `app/api/`, `app/schemas/`, `app/db/seed.py` y `requirements.txt`.
- **Frontend:** `apps/frontend/` completo.
- **Contenido:** `content/toefl-ibt-2026-b1-b2/` (U1, diagnóstico,
  registros) y `content/_legacy/`.
- **E2E:** `e2e/`.
- **Docs:** `docs/api/openapi.json`, `docs/contenido/cobertura.md`,
  `docs/runbook.md`, `docs/reviews/mvp-01-*.md` y una marca de histórico en
  `docs/REQUIREMENTS.md`.

## Definition of Done

- [ ] **AC-01** — `make verify` termina con 0 en una sesión cloud nueva
  después del bootstrap (output literal en el PR de cierre).
- [ ] **AC-02** — `ci-gate` en verde en el SHA de cierre, con todos los
  jobs de REQ-02.
- [ ] **AC-03** — Las migraciones pasan desde base vacía y desde el esquema
  legado con su seed; `alembic check` limpio.
- [ ] **AC-04** — Los contratos de import-linter pasan, y la violación
  provocada en el fixture hace fallar al linter.
- [ ] **AC-05** — Invitación de un solo uso, con vencimiento y sin rol
  elegible; login y logout; sesión revocada al cerrar sesión y al hacer
  reset (pruebas).
- [ ] **AC-06** — Aislamiento: prueba negativa con dos cuentas en cada
  endpoint con datos de alumno, listados en la prueba (404).
- [ ] **AC-07** — CSRF: método no seguro sin token o con token incorrecto →
  403; `Origin` ajeno → 403 (pruebas).
- [ ] **AC-08** — Ningún DTO de alumno incluye soluciones, explicaciones,
  variantes aceptadas, pistas ni rúbricas privadas antes de enviar: una
  prueba de contrato recorre las respuestas de todos los endpoints de
  alumno buscando claves prohibidas.
- [ ] **AC-09** — Idempotencia: misma clave y mismo cuerpo → mismo
  resultado y una sola fila; misma clave y cuerpo distinto → 409; dos
  envíos concurrentes con la misma clave → un solo intento (prueba con dos
  hilos).
- [ ] **AC-10** — Corrección por formato con variantes válidas (varios
  órdenes, completados alternativos) en pruebas de dominio.
- [ ] **AC-11** — Editorial: editar crea una revisión nueva; la aprobación
  se ata al hash; publicar se bloquea con hallazgos materiales, errores de
  lint, audio sin revisar o hash distinto; publicar y retirar son atómicos;
  los intentos históricos conservan su revisión.
- [ ] **AC-12** — Repaso 1/3/7 con reinicio y ayudas que no avanzan
  (dominio con reloj falso); intento y repaso en una transacción (una falla
  provocada después del insert revierte ambos).
- [ ] **AC-13** — Las métricas coinciden con un fixture controlado
  (números exactos), incluidos duplicados que no inflan avance ni racha.
- [ ] **AC-14** — E2E en la CI: invitación → aceptación con consentimiento
  → diagnóstico (subconjunto) → L1: respuesta, pista, fallo y acierto →
  recarga con respuestas persistidas → reinicio del servidor sin pérdida →
  reloj +24 h → repasos vencidos → logout. Una segunda cuenta no ve los
  intentos de la primera. Un admin publica una revisión nueva y el
  historial anterior queda intacto.
- [ ] **AC-15** — El flujo principal pasa con viewport de teléfono y solo
  con teclado; axe sin violaciones graves ni críticas en las pantallas de
  acceso, inicio, ruta, lección, comprobación y resultados.
- [ ] **AC-16** — Contenido U1 (4 lecciones, escenario, checkpoint) y
  diagnóstico pasan lint y mínimos; `cobertura.md` al día; sin marcadores;
  guiones de audio presentes; todo en `ready-for-review`;
  `docs/contenido/revision/u1.md` generado.
- [ ] **AC-17** — La imagen de producción construye y arranca con el
  comando de `heroku.yml`: `/health` 200, `/api/v1/ready` 200 con base de
  datos, `/` sirve la SPA, `/api/v1/no-existe` → 404 JSON y un asset
  inexistente → 404.
- [ ] **AC-18** — El bundle no contiene llaves ni hosts de proveedores
  (grep en la CI).
- [ ] **AC-19** — Cabeceras de seguridad y atributos de la cookie
  verificados por prueba; Markdown con HTML crudo no se renderiza como
  HTML.
- [ ] **AC-20** — El resultado del smoke de rendimiento está registrado en
  `docs/reviews/mvp-01-verify.md` y cumple NFR-03 o tiene desviación
  registrada.
- [ ] **AC-21** — `deploy.yml` pasa actionlint; tras el merge que lo
  introduce, su run en `main` queda omitido (sin `DEPLOY_ENABLED`) y no en
  verde (URL del run). El caso "deploy no configurado" se comprueba en G1.
- [ ] **AC-22** — Exportación y borrado de cuenta funcionan y quedan
  probados; después del borrado no queda ninguna fila del usuario.
- [ ] **AC-23** — Panel del piloto y feedback por lección muestran datos de
  un fixture con cuentas internas excluidas.
- [ ] **AC-24** — Docs al día: `HANDOFF.md`, `STATE.md`, `docs/runbook.md`,
  `docs/reviews/mvp-01-verify.md` (formato `verify`) y
  `docs/reviews/mvp-01-activacion-cto-review.md` (gates G1–G4).

---

## Enmiendas

Ninguna todavía.
