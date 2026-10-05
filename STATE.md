# STATE.md — ciclo activo

**Fase:** MVP-01 por iniciar. G0 aprobado por Jonathan el 5 oct 2026
(PR #2).
**Siguiente change set:** MVP-01 CS-01 · Base reproducible y CI mínima
(`docs/plans/mvp-01-nucleo-piloto-plan.md`).
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
- Environment cloud `pcre` creado por Jonathan (red Trusted, sin llaves,
  timeouts ampliados) `[inherited-unverified]`.

## Registro de change sets

| Ciclo | CS | Rama | PR | SHA mergeado | Run de CI | Evidencia | Fecha |
|---|---|---|---|---|---|---|---|
| — | paquete G0 | `docs/sdd-mvp-specs` | [#2](https://github.com/astraDukoWave/pcre-learning-platform/pull/2) | se completa en CS-01 | sin CI (la crea CS-01) | aprobación de Jonathan (G0) | 5 oct 2026 |

## Desviaciones

Ninguna.

## Loop humano vigente

1. Lanzar la sesión cloud con el prompt del §2 de `claude/prompts-arranque.md`
   (Proyecto privado "English StartUp").
2. **H-1b:** cuando el PR de CS-01 muestre el check `ci-gate`, agregarlo
   como requerido en el ruleset (pasos en el plan de MVP-01, "Tareas
   [HUMANO]").

*Última actualización: 5 oct 2026 (G0 aprobado).*
