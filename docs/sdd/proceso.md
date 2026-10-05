# Proceso SDD de PCRE — cómo trabaja el agente

Versión 1.0 · 5 oct 2026. Resume la metodología de una sola ventana
(heredada de CareerAI, `HANDOFF.md` §7 @ `0db81a1`) y la adapta a
ejecuciones autónomas en sesiones cloud de Claude Code. Si las skills del
flujo SDD (`workflow-router`, `brainstorm`, `design-spec`,
`system-design-spec`, `design-plan`, `verify`, `cto-review`) están
disponibles en la sesión, se cargan en su etapa; si no, este documento
basta.

---

## 1. Roles

- **Jonathan:** aprueba specs y planes, firma los gates, maneja secretos,
  aprueba deploys, publica contenido, invita personas y hace las pruebas
  con navegador real, micrófono o teléfono.
- **Claude (esta sesión):** CTO y ejecutor. Implementa los planes
  aprobados, verifica con evidencia ejecutable y deja el estado escrito.
- **Verificador independiente:** subagente de contexto fresco que solo
  recibe spec, diff y evidencia (ver §8). Obligatorio donde el plan lo
  diga.

## 2. Ciclo

`brainstorm → design-spec (+ system-design-spec) → design-plan → ejecución
→ verify → cto-review (si hay acciones de alto riesgo) → release`.

Lanes: **Fast** (fix dentro de un spec aprobado o solo docs), **Standard**
(feature con spec y plan) y **High-risk** (Standard + `cto-review` antes de
cada acción de alto riesgo y verificador independiente).

## 3. Gates

| Gate | Qué autoriza | Quién firma | Dónde se documenta |
|---|---|---|---|
| G0 | Paquete de specs y planes; arranque autónomo; delegación de merges | Jonathan | `docs/reviews/g0-arranque-autonomo-cto-review.md` |
| G1 | Deploy a Heroku (primer deploy y siguientes, con aprobación del environment) | Jonathan | `docs/reviews/mvp-01-activacion-cto-review.md` |
| G2 | Generar audio con TTS (un run por unidad) | Jonathan | ídem |
| G3 | Publicar contenido para alumnos (por unidad) | Jonathan | ídem |
| G4 | Invitar alumnos reales y guardar sus datos | Jonathan | ídem |
| G5 / G5a | Encender IA y voz con presupuestos / correr el benchmark del feedback | Jonathan | `docs/reviews/mvp-02-activacion-cto-review.md` |
| G6 | Arrancar MVP-03 (U1 revisada, examen confirmado) | Jonathan | `STATE.md` |

El agente nunca firma un gate ni ejecuta la acción que cubre.

## 4. Un change set, paso a paso

1. **Estado real.** `git fetch origin main`; SHA de `origin/main`; PRs
   abiertos (`gh api "repos/astraDukoWave/pcre-learning-platform/pulls?state=open"`);
   ruleset (`gh api repos/astraDukoWave/pcre-learning-platform/rules/branches/main`).
   Si `STATE.md` contradice el repo, manda el repo y se registra la
   diferencia.
2. **Rama** desde `origin/main` (o desde la rama del change set anterior si
   se apila) con el nombre del plan.
3. **Implementación** con pruebas desde el inicio. Antes de cada push, las
   pruebas del área y, antes de abrir el PR, `make verify` (o lo que exista
   de él en ese punto).
4. **Commits** pequeños con Conventional Commits. Push en cada checkpoint
   verde y siempre antes de terminar un turno: nada vive solo en el working
   tree.
5. **PR por REST** (GraphQL no está disponible):
   `gh api repos/astraDukoWave/pcre-learning-platform/pulls -f title='…' -f head='<rama>' -f base=main -F body=@/tmp/pr-body.md`.
   El cuerpo usa la plantilla del §9.
6. **CI:** esperar a que termine `ci-gate` para el SHA del head
   (`gh api "repos/astraDukoWave/pcre-learning-platform/commits/<sha>/check-runs?check_name=ci-gate"`).
   Si falla, leer el log, corregir y repetir. Tras tres intentos fallidos
   por la misma causa, registrar una desviación.
7. **Verificador independiente** si el plan lo pide (§8); sus hallazgos van
   al PR como comentario y se corrigen antes del merge.
8. **Merge** (solo con la delegación de G0 y si se cumplen las tres
   condiciones del plan):
   `gh api -X PUT repos/astraDukoWave/pcre-learning-platform/pulls/<n>/merge -f merge_method=merge -f sha=<head_sha>`.
   Nunca squash ni rebase: los planes citan SHAs.
9. **Registro:** al abrir el PR, agregar su línea en `STATE.md` (CS, rama,
   PR). En el primer commit del change set siguiente, completar el SHA
   mergeado y la URL del run de CI.

## 5. Evidencia

Jerarquía (de más fuerte a más débil): run de CI ligado al SHA exacto →
ejecución en la sesión con output literal → inspección del árbol o diff del
SHA remoto → reporte sin artefacto.

Etiquetas: `[verified-this-session]` · `[ci-run]` · `[inherited-unverified]`
· `[contradicted]`. Nunca se acepta "los tests pasaron" sin el run o el
output. Lo que no se pudo comprobar se declara, no se esconde.

## 6. Desviaciones (modo autónomo)

Una desviación es cualquier diferencia entre lo que el spec o el plan
piden y lo que se puede o conviene hacer.

1. Detenerse en ese punto y registrarla en `STATE.md` → "Desviaciones":
   `DV-nn · qué · por qué · opciones · disposición: pending-human`.
2. Seguir con el trabajo que no depende de ella.
3. Detener la ejecución solo si todo lo restante depende de la decisión;
   en ese caso, cerrar con "Estado del ciclo" y "Loop humano".
4. Disposiciones válidas, siempre decididas por Jonathan: `correct`,
   `ratify-with-reason` o `rollback`.

Ajustes del plan que no cambian alcance ni contrato (nombre de un archivo,
orden de commits dentro de un change set) se registran como nota del change
set, no como desviación.

## 7. Bloqueos frecuentes

- **Falta una acción humana** (ruleset, secretos, aprobación): Loop humano
  en `STATE.md` y seguir con lo independiente; los PR se apilan si no se
  puede mergear.
- **Contexto compactado o sesión nueva:** releer `CLAUDE.md`, `STATE.md` y
  el change set en curso del plan antes de seguir.
- **Límite de uso del plan de Claude:** el trabajo queda pusheado; `/goal`
  retoma cuando se restablece. Nunca dejar cambios sin push al final de un
  turno largo.
- **Comando largo:** `BASH_DEFAULT_TIMEOUT_MS` del environment o correrlo
  en segundo plano y revisar su salida.

## 8. Verificador independiente (plantilla)

Lanzar un subagente con solo esto:

> Eres un verificador independiente. Spec: `<ruta>` @ `<sha>` (lee las
> secciones REQ, NFR y AC que cubre el change set `<CS>`). Diff: `git diff
> <base>...<head>` en el repo local. Evidencia: `<URL del run de CI>` y
> `<output pegado>`. Para cada AC del change set responde: ✅ con evidencia,
> ❌ con el hallazgo exacto (archivo y línea) o ⏸ si falta evidencia. Busca
> en particular fugas de soluciones o secretos, aislamiento entre usuarios,
> transacciones y casos edge del spec. No propongas trabajo fuera del spec.

## 9. Plantillas

**Cuerpo de PR:**

```markdown
## <CS-nn> · <nombre>
Spec: docs/specs/<archivo>.md @ <sha> · Plan: docs/plans/<archivo>.md
### Qué cambia
### Evidencia
- CI: <se completa al terminar>
- Local: <comandos y output resumido>
### AC cubiertos
### Riesgos y notas
### Verificador independiente (si aplica)
```

**Estado del ciclo** (cierre de cada etapa, sustituye al transition packet):

```
## Estado del ciclo — <ciclo> · etapa: <etapa> (<estado>)
Artefactos: <ruta @ SHA corto>
Evidencia: <etiqueta + dónde>
Desviaciones: ninguna / <DV-nn · qué · disposición>
Siguiente: <etapa> → <skill> · lane <Fast | Standard | High-risk>
```

**Loop humano** (si hay acciones de Jonathan; comandos exactos, sin
suponer nada de su estado):

```
## Loop humano
1. <acción> — <dónde> — <comando o texto exacto>
Devuélveme: <la evidencia concreta>
```

**Reporte de verify** (`docs/reviews/<ciclo>-verify.md`): secciones 1.
Código vs. spec (por AC, con etiqueta) · 2. Tests automatizados · 3.
Contratos y casos edge · 4. QA de producto / E2E (o pendiente humano) · 5.
Smoke de deployment (si aplica) · 6. Proceso · Regresiones · Deuda
introducida · Decisión (✅ listo · ⏸ pendiente de evidencia humana · ❌
requiere correcciones).

**Dictamen cto-review** (`docs/reviews/<gate>-cto-review.md`):
clasificación por acción · matriz de verificaciones · veredicto con
cambios numerados · rollback, blast radius, dueño y observabilidad ·
hasta 3 decisiones para Jonathan (TL;DR, qué gana, qué paga,
recomendación, pregunta cerrada) · mensaje de aprobación listo para pegar
· registro del gate en JSON.

## 10. Reglas del repo público

- Sin secretos, llaves, tokens, cookies ni URLs con credenciales: solo
  placeholders.
- Sin datos de clientes ni de alumnos (nombres, correos, respuestas,
  transcripciones), ni siquiera en fixtures.
- Sin estrategia comercial, precios objetivo ni análisis de competidores:
  viven en `strategy.md` (privado, Proyecto "English StartUp") y aquí solo
  se citan por nombre.
- El contenido de práctica es original y se publica con la licencia que
  decida Jonathan (decisión abierta en el spec de MVP-01).
