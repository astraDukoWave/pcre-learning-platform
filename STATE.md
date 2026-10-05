# STATE.md — ciclo activo

**Fase:** gate **G0 pendiente**. El paquete de specs y planes está en la
rama `docs/sdd-mvp-specs` (PR #2 a `main`), esperando la firma de
Jonathan.
**Siguiente ciclo:** MVP-01 (`docs/plans/mvp-01-nucleo-piloto-plan.md`),
al firmarse G0.

## Gates

| Gate | Qué autoriza | Estado |
|---|---|---|
| G0 | Paquete MVP-01/02/03; arranque autónomo; delegación de merges | **pendiente** |
| G1 | Deploy a Heroku | no iniciado |
| G2 | Audio TTS por unidad | no iniciado |
| G3 | Publicación de contenido por unidad | no iniciado |
| G4 | Alumnos reales | no iniciado |
| G5 / G5a | IA y voz / benchmark del feedback | no iniciado |
| G6 | Arranque de MVP-03 | no iniciado |

**Delegación de merges:** ninguna hasta que G0 la firme (decisión 1).
**Ruleset de `main`:** sin configurar (`rules/branches/main` devuelve
`[]`, 5 oct 2026). H-1 pendiente.

## Decisiones pendientes de Jonathan

Las tres de `docs/reviews/g0-arranque-autonomo-cto-review.md`:

1. Delegar los merges a `main` (CI verde + ruleset) en MVP-01 y MVP-02.
2. Encadenamiento de ciclos (recomendado: un `/goal` para MVP-01 + MVP-02;
   MVP-03 tras G6) y examen objetivo de los primeros clientes, si ya se
   conoce.
3. Techo de gasto mensual del piloto (IA y voz) y plan del dyno.

## Registro de change sets

| Ciclo | CS | Rama | PR | SHA mergeado | Run de CI | Evidencia | Fecha |
|---|---|---|---|---|---|---|---|
| — | paquete G0 | `docs/sdd-mvp-specs` | [#2](https://github.com/astraDukoWave/pcre-learning-platform/pull/2) | — | sin CI todavía (la crea MVP-01 CS-01) | revisión humana del paquete | 5 oct 2026 |

## Desviaciones

Ninguna.

## Loop humano vigente

1. Revisar el PR del paquete y firmar G0 (mensaje en el dictamen).
2. H-1: ruleset de `main` (pasos exactos en el plan de MVP-01, "Tareas
   [HUMANO]").
3. Lanzar la sesión cloud con el prompt `/goal` del Proyecto privado.

*Última actualización: 5 oct 2026.*
