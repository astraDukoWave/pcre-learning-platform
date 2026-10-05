# Dictamen CTO: arranque autónomo del MVP — gate G0

- **Ciclos:** MVP-01, MVP-02 y MVP-03.
- **Artefactos revisados:** specs, `docs/arquitectura.md` y
  `docs/contenido/contrato-curricular.md` @ `9aa2e2c`; planes y documentos
  del agente @ `0100c0a` (rama `docs/sdd-mvp-specs`).
- **Fecha:** 5 oct 2026. Skill: `cto-review` v0.2.
- **Firma:** Jonathan. Este dictamen no aprueba por él.

## Clasificación por acción

| Acción | Clase | Gate |
|---|---|---|
| Lanzar una sesión cloud con `/goal` que escriba código, pruebas, contenido borrador y docs en ramas con PR | Rutina: sin producción, sin dinero y sin secretos | G0 |
| Delegar en el agente el merge a `main` con CI verde (MVP-01 y MVP-02) | **Alto** (permisos amplios para un agente) | G0, decisión 1 |
| Crear workflows que después podrán desplegar o gastar (`deploy.yml`, `content-audio.yml`, `feedback-eval.yml`) | Rutina mientras no tengan secretos; su activación es Alto | G1, G2 y G5a |
| Consumir horas de uso del plan de Claude | Rutina: sin cobro extra por la VM, comparte los límites del plan | Informativo |
| Versionar lecciones y claves de respuesta en un repo público | Decisión abierta (propiedad intelectual e integridad de las comprobaciones) | Supuesto con trigger (LB-09) |
| `.claude/settings.json` con reglas `deny` | Rutina (reduce riesgo) | Este PR |

## Verificaciones (matriz)

| Claim | Fuente | Resultado |
|---|---|---|
| `main` @ `133c5e3` es la base que inspeccionó el discovery | `git ls-remote` y clon | `[verified-this-session]` |
| El repo es público; no tiene workflows ni rulesets; la protección clásica y los environments no se leen desde la sesión | API REST de GitHub (`rules/branches/main` = `[]`, workflows = 0, 403 en protección y environments) | `[verified-this-session]` |
| GraphQL no está disponible: los PR se abren y se mergean por REST | Respuesta del proxy de la sesión | `[verified-this-session]` |
| Auto mode permite por defecto pushes a la rama default; las reglas `deny` del repo aplican antes del clasificador | code.claude.com/docs/en/auto-mode-config | `[verified-this-session]` |
| La VM cloud trae PostgreSQL 16, Docker, Node 22 y uv; su red Trusted no incluye Heroku ni Deepgram | code.claude.com/docs/en/cloud-environments | `[verified-this-session]` (documentación; CS-01 lo confirma en ejecución) |
| `/goal` sigue hasta que un evaluador confirma la condición con lo que aparece en la conversación; máximo 4 000 caracteres | code.claude.com/docs/en/goal | `[verified-this-session]` |
| Tareas del TOEFL iBT 2026 | ets.org, página de contenido | `[verified-this-session]` |
| Precios y mensajes de Deepgram; modelos administrados | deepgram.com/pricing y referencia de la Voice Agent API | `[verified-this-session]` |
| Heroku: sintaxis de `heroku.yml`, release phase, Essential-0 | devcenter.heroku.com | `[verified-this-session]` |
| Patrones de CareerAI (CI con arranque de imagen, flags de uvicorn, Deepgram falso) | Repo `career-ai` @ `0db81a1` | `[verified-this-session]` |
| La memoria registra un "Auth Core (bcrypt + JWT)" de la fase 1.5 | Ninguna rama remota lo contiene | `[contradicted]` |
| Las skills de la cuenta estarán disponibles en la sesión cloud | — | `[inherited-unverified]`; respaldo en `docs/sdd/proceso.md` |
| El plan de Claude alcanza para muchas horas seguidas | — | `[inherited-unverified]`; `/goal` se pausa y retoma con los límites |
| Los primeros clientes necesitan TOEFL iBT | — | `[inherited-unverified]` → decisión 2 |

## Veredicto: APROBAR CON CAMBIOS

Los cambios son pasos de configuración; no hace falta tocar los documentos.

1. **Activar el ruleset de `main` (H-1) antes del primer merge del
   agente.** *Por qué:* hoy GitHub no exige ningún check y auto mode
   permite empujar a la rama default. El agente comprueba el ruleset por
   API antes de cada merge; sin él, apila los PR y no mergea.
2. **Crear un environment cloud propio para PCRE, sin secretos.** Red
   **Trusted**, variables `BASH_DEFAULT_TIMEOUT_MS=600000` y
   `BASH_MAX_TIMEOUT_MS=1200000`, y modo **Auto** al iniciar la sesión.
   *Por qué:* instalaciones y builds pasan de los 2 minutos por defecto; las
   variables de un environment las lee cualquiera que lo use, y el agente
   no debe tener llaves de pago.
3. **Ninguna llave de Heroku, Deepgram o Gemini antes de su gate** (G1, G2,
   G5a, G5). *Por qué:* el plan se verifica completo con dobles de prueba;
   una llave temprana solo agrega riesgo de costo.

## Requisitos de alto riesgo (delegación de merges)

- **Rollback:** cada merge es un merge commit; se revierte con un PR de
  `git revert -m 1 <sha>`. Hasta G1 nada se despliega, así que un merge
  equivocado no afecta a nadie.
- **Blast radius:** el contenido de `main` (código, docs y contenido en
  borrador). Sin usuarios, sin producción y sin dinero hasta G1, G2 y G5.
- **Dueño:** Jonathan delega; Claude ejecuta. La delegación se revoca en
  cualquier momento con un mensaje a la sesión o editando `STATE.md`.
- **Observabilidad:** registro de change sets en `STATE.md`; PRs y runs de
  CI en GitHub (también desde el teléfono); trailer `Claude-Session` en
  cada commit; la sesión en claude.ai/code o en la app.

## Decisiones que son tuyas

1. **¿Delegas en Claude los merges a `main` durante MVP-01 y MVP-02?**
   - *TL;DR:* para trabajar horas sin esperarte, el agente necesita
     mergear sus PR cuando la CI está en verde. Sin delegación, deja unos
     20 PR apilados para que los mergees tú.
   - *Ganas:* avance continuo; cada change set se construye sobre el
     anterior ya verificado. Es el mismo acuerdo que tienes en CareerAI.
   - *Pagas:* el código entra a `main` sin tu revisión línea por línea (la
     cubren CI, ruleset y verificadores independientes). Producción no se
     toca: cada deploy sigue esperando tu aprobación (G1).
   - *Recomendación:* sí, con el ruleset activo.
   - **Pregunta cerrada:** ¿delegas? (sí/no)
2. **¿Cómo encadenamos los ciclos?**
   - *TL;DR:* propongo un solo `/goal` para MVP-01 y MVP-02 (plataforma,
     U1, coach) y que MVP-03 (las 28 lecciones de U2–U8) espere a que
     revises U1 y me confirmes qué examen necesitan tus primeros clientes.
   - *Ganas:* si el estilo de U1 necesita cambios, o si una clienta
     necesita otro examen (por ejemplo TOEFL ITP o Cambridge), lo sabemos
     antes de producir 28 lecciones; mientras tanto, tus clientes ya
     practican con U1.
   - *Pagas:* una segunda sesión con su propio prompt cuando firmes G6.
   - *Recomendación:* A.
   - **Pregunta cerrada:** A (MVP-01 + MVP-02 ahora, MVP-03 tras G6) · B
     (los tres en un solo `/goal`) · C (solo MVP-01). Si ya sabes qué examen
     necesita tu primera clienta, dímelo y lo registro.
3. **¿Qué techo de gasto autorizas para el piloto?**
   - *TL;DR:* el feedback con IA y el coach de voz cobran por uso. El
     código llega apagado y con topes; necesito tus números para dejarlos
     como valores por defecto (se activan en G5).
   - *Referencias (5 oct 2026):* voz USD 0.075 por minuto (una sesión de 5
     minutos, USD 0.375; 3 alumnos con 20 sesiones al mes, USD 22.50);
     feedback de texto, centavos por respuesta; audio de una unidad con TTS,
     alrededor de USD 1. Heroku: un dyno Basic (no se duerme) en lugar de
     Eco (se duerme tras 30 minutos sin uso y tarda unos segundos en
     despertar) `[inherited: spec de producto v0.3]`, pagado con tus
     créditos.
   - *Recomendación:* tope global de USD 25 al mes, USD 8 por alumno al
     mes, 60 minutos de voz por alumno al mes y dyno Basic.
   - **Pregunta cerrada:** ¿aceptas esos topes y Basic? (sí / otros
     números)

## Mensaje de aprobación (pegar en esta conversación)

> Apruebo G0 para el paquete del PR de `docs/sdd-mvp-specs`: specs
> MVP-01/02/03 @ `9aa2e2c` y planes @ `0100c0a`, con la arquitectura y el
> contrato curricular. Ratifico ADR-08 (tablas nuevas para el currículo) y
> la división en tres ciclos. Decisión 1: [sí/no] delego en Claude el merge
> a `main` con merge commit cuando `ci-gate` esté en verde y el ruleset de
> `main` esté activo, solo para MVP-01 y MVP-02; deploys, secretos,
> publicación de contenido e invitaciones siguen siendo míos. Decisión 2:
> [A/B/C]. Decisión 3: [USD 25 global, USD 8 por alumno, 60 min de voz por
> alumno, dyno Basic | otros números]. Los ajustes del plan que no cambien
> alcance ni contrato se registran en `STATE.md`; cualquier otra desviación
> queda `pending-human`.

## Registro del gate

```json
{
  "gate_id": "G0",
  "cycle_id": "MVP-01..MVP-03",
  "artefacto": "docs/sdd-mvp-specs: specs @ 9aa2e2c, planes @ 0100c0a (docs/reviews/g0-arranque-autonomo-cto-review.md)",
  "veredicto": "APROBAR CON CAMBIOS",
  "condiciones": [
    "H-1: ruleset de main activo antes del primer merge del agente",
    "environment cloud propio, red Trusted, timeouts ampliados, sin secretos, modo Auto",
    "ninguna llave de pago antes de su gate"
  ],
  "respuesta_humana": "pendiente"
}
```

## Estado del ciclo — MVP-01..03 · etapa: G0 (pendiente de aprobación)

- **Artefactos:** `docs/specs/*` @ `9aa2e2c` · `docs/plans/*` @ `0100c0a` ·
  este dictamen.
- **Evidencia:** matriz de arriba (`[verified-this-session]` salvo lo
  marcado).
- **Desviaciones:** ninguna abierta; ADR-08 y la división en tres ciclos
  se presentan para ratificar.
- **Siguiente:** ejecución de MVP-01 → `design-plan` ya aprobado con G0 ·
  lane Standard.
