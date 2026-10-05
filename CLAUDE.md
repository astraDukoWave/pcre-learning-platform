@AGENTS.md

# CLAUDE.md — instrucciones para Claude Code

Este archivo complementa `AGENTS.md` (importado arriba) con las reglas del
agente autónomo. Procedimiento completo y plantillas:
`docs/sdd/proceso.md`.

## Antes de tocar nada

1. Lee `HANDOFF.md` (fuente de verdad) y `STATE.md` (ciclo activo, gates,
   registro de change sets, desviaciones).
2. Comprueba el repo real: `git fetch origin main`, SHA de `origin/main`,
   PRs abiertos y ruleset (comandos en `docs/sdd/proceso.md` §4). Si
   `STATE.md` contradice al repo, manda el repo.
3. Ubica el ciclo y el siguiente change set en `docs/plans/`. El plan cita
   el spec @ SHA: trabaja contra esa versión.
4. Si las skills del flujo SDD están disponibles, cárgalas en su etapa
   (`design-plan`, `verify`, `cto-review`); si no, sigue
   `docs/sdd/proceso.md`.

## Reglas duras

- **Nunca** despliegues, ni corras la CLI de Heroku, ni hagas `git push` a
  un remoto de Heroku.
- **Nunca** crees, leas, pidas ni escribas secretos; en el repo solo van
  placeholders.
- **Nunca** llames APIs de pago (Deepgram, Gemini u otras). Usa los dobles
  de prueba. No dispares `content-audio.yml` ni `feedback-eval.yml`.
- **Nunca** publiques contenido para alumnos, apruebes revisiones con un
  revisor real ni invites personas. El revisor `fixture:dev` solo existe en
  `dev` y `test`.
- **Nunca** hagas push directo ni force push a `main`, ni squash o rebase
  al mergear. Todo entra por PR con merge commit.
- **Nunca** cambies ajustes del repo (rulesets, environments, secrets,
  variables).
- **Nunca** amplíes el alcance fuera del spec aprobado: lo nuevo va al
  Learning Backlog de `HANDOFF.md` o se registra como desviación.
- **Repo público:** nada de datos de clientes, alumnos ni estrategia
  comercial (`docs/sdd/proceso.md` §10).

## Merges

Solo si G0 delegó los merges para el ciclo en curso (ver `STATE.md`) y se
cumplen las tres condiciones del plan: `ci-gate` verde en el SHA del head,
ruleset de `main` activo y ninguna desviación `pending-human` que afecte al
change set. Si no, apila el PR y sigue.

## Trabajo por change set

Rama del plan → pruebas desde el inicio → `make verify` → push → PR por
REST → CI → verificador independiente si el plan lo pide → merge → línea en
`STATE.md`. Push en cada checkpoint verde y siempre antes de terminar un
turno.

## Evidencia

Run de CI ligado al SHA > output literal en la sesión > inspección del
diff > reporte. Etiquetas: `[verified-this-session]`, `[ci-run]`,
`[inherited-unverified]`, `[contradicted]`. Nada se marca ✅ sin evidencia.

## Cuando algo bloquea

Registra la desviación o el paso humano en `STATE.md`, sigue con lo
independiente y detente solo si todo lo restante depende de eso. Cierra
cada etapa con los bloques "Estado del ciclo" y, si hace falta, "Loop
humano" (`docs/sdd/proceso.md` §9).

## Zonas que no se tocan sin spec

- Tablas e historia de Alembic existentes: solo migraciones *expand*.
- `heroku.yml` y `Dockerfile`: la CI arranca la imagen con ese comando;
  cualquier cambio pasa por su job `image`.
- Desde MVP-02: el relay de voz y los presupuestos (`app/modules/coaching/voice/`,
  `app/modules/usage/`) llaman o acotan APIs de pago; cambios con spec y
  `cto-review`.
