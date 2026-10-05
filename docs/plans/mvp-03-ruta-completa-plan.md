# Plan: mvp-03-ruta-completa

- **plan_id:** MVP-03-PLAN-01
- **Spec:** `docs/specs/mvp-03-ruta-completa.md` @ `9aa2e2c`
  (MVP-03-SPEC-01; sha256
  `5031bd04447b2e2ab8dffc23efad06d41f548b466d715d338eedb8df32957886`).
- **Precondición:** gate **G6** firmado por Jonathan (U1 revisada y meta de
  examen de los primeros clientes confirmada). Si G6 cambia la ruta
  prioritaria, primero se enmienda el spec.
- **Ramas:** `feat/mvp03-csNN-<unidad>`, una por change set, con PR a
  `main`.
- **Lane:** Standard. Publicar (G3) y generar audio (G2) son de Jonathan.
- **Estado:** **PENDIENTE DE APROBACIÓN** (gate G0).

---

## Contexto de dominio (con procedencia)

- **D1 · Contrato curricular** @ `9aa2e2c`: mapa de unidades (§4), mínimos
  (§5), reglas de redacción (§6), escenarios (§7), rúbricas (§8), formato
  (§9), cobertura (§10), audio (§11) y flujo editorial (§12).
- **D2 · Formato TOEFL iBT 2026**: contrato §2 *(ets.org, 5 oct 2026)*.
- **D3 · Herramientas que deja MVP-01:** `make content-lint`,
  `make review-packet`, `content-audio.yml`, el panel editorial y la
  revisión fijada.
- **D4 · Lo aprendido en U1:** hallazgos de `review_findings`, decisiones
  de `editorial_decisions` y feedback del piloto. Se destila en la guía de
  estilo (CS-01); no se copia texto de alumnos al repo.

## Cumplimiento de proceso

Igual que MVP-01-PLAN-01. Además:

- Un PR por unidad, con contenido, guiones y paquete de revisión.
- Nunca se marca un ítem `ready-for-review` con advertencias del lint sin
  explicar en el PR.
- El run de audio de cada unidad se pide en el Loop humano con el costo
  estimado por `generate_audio.py --dry-run`.

## Change sets

### CS-01 · Guía de estilo

- **Archivos:** `docs/contenido/guia-de-estilo.md`; reglas nuevas en el
  lint de contenido cuando se puedan automatizar.
- **Qué hacer:** convertir cada hallazgo de la revisión de U1 en una regla
  con su origen (id del hallazgo o de la decisión); ajustar U1 si una regla
  nueva lo exige (revisión nueva en borrador).
- **Verificación:** pruebas de las reglas nuevas del lint; la guía cita su
  origen en cada regla.
- **Commit:** `docs(content): style guide from U1 review`.

### CS-02 a CS-08 · Unidades 2 a 8

Un change set por unidad, en orden (U2 … U8). Cada uno:

- **Archivos:** `content/toefl-ibt-2026-b1-b2/units/u<n>-<slug>/{l1-lectura,l2-escucha,l3-escritura,l4-habla,escenario,checkpoint}.yaml`,
  entradas en `audio/manifest.yaml` (solo guiones), `sources.yaml`,
  `docs/contenido/revision/u<n>.md` y `docs/contenido/cobertura.md`.
- **Qué hacer:** cuatro lecciones con los objetivos y familias del contrato
  §4, mínimos del §5, extensiones y apoyo en español del §6 y la guía de
  estilo; escenario con grafo de texto y configuración del coach;
  checkpoint con ítems nuevos; guiones de audio; segunda pasada con la
  lista de revisión del §12; paquete de revisión.
- **Verificación:** lint y cobertura sin errores `[ci-run]`; `generate_audio.py
  --dry-run` con el conteo y el costo en el PR.
- **Commit:** `feat(content): unit <n> drafts ready for review`.

### CS-09 · Formulario final, comparación y ruta completa

- **Archivos:** `content/…/assessments/final.yaml`; servicio y endpoint de
  comparación en `progress`; cálculo de `route_complete`;
  `apps/frontend/src/features/results/initial-vs-final/`; pruebas.
- **Qué hacer:** REQ-05 y REQ-07: formulario final disjunto con el mismo
  reparto que el inicial; vista "Inicial y final" con el texto formativo
  fijo; `route_complete` calculado por el sistema y visible en el panel y,
  cuando es verdadero, para el alumno.
- **Verificación:** AC-02, AC-05 y AC-06.
- **Commit:** `feat(progress): final form comparison and route
  completeness`.

### CS-10 · Cierre de MVP-03

- **Qué hacer:** `docs/reviews/mvp-03-verify.md`; smoke de rendimiento con
  8 unidades (NFR-03); `HANDOFF.md` y `STATE.md`; checklist de M2 para
  Jonathan (AC-09).
- **Verificación:** AC-01, AC-03, AC-04, AC-07 y AC-08.
- **Commit:** `docs: close MVP-03 with verify report`.

## Tareas [HUMANO]

- **G6 · Arranque** (antes de CS-01): confirmar la meta de examen de los
  primeros clientes y que U1 ya se revisó. Mensaje: "Apruebo G6: la ruta
  prioritaria sigue siendo TOEFL iBT 2026 (o: cambia a ___); U1 revisada."
- **G2 · Audio por unidad:** aprobar el run de `content-audio.yml` de cada
  unidad y revisar su PR de MP3. Evidencia: URL del run y PR mergeado.
- **G3 · Publicación por unidad:** revisar en el panel con
  `docs/contenido/revision/u<n>.md`, registrar hallazgos, aprobar y
  publicar. Anotar en la decisión de aprobación cuánto tiempo tomó.
- **AC-09 · M2:** con U8 publicada, confirmar que el panel muestra la ruta
  completa.

## Orden y dependencias

```
G6 ─ CS-01 ─ CS-02 ─ CS-03 ─ … ─ CS-08 ─ CS-09 ─ CS-10
              │       │             │
              G2/G3   G2/G3         G2/G3   (por unidad, en paralelo a la escritura de la siguiente)
```

La escritura de una unidad no espera la publicación de la anterior. Si una
revisión cambia la guía de estilo, la unidad en curso se ajusta antes de
cerrar su change set.

## Tests requeridos

| Qué | Dónde |
|---|---|
| Lint, mínimos y cobertura de cada unidad | job `content` |
| Paquetes de revisión al día | job `content` |
| Disjunción de formularios y mismo reparto | pytest |
| Vista comparativa con fixture | pytest + E2E |
| `route_complete` con cada condición fallando | pytest |
| Rendimiento con 8 unidades | `scripts/perf/smoke.py` |

## Riesgos → mitigación

- **Calidad que decae en la unidad 6 o 7** → guía de estilo, segunda pasada
  obligatoria, revisión por lotes y métricas por unidad.
- **Cuello de botella editorial** → paquetes de revisión; publicar unidad
  por unidad sin frenar la escritura; trigger de revisión asistida (LB-04)
  si una unidad toma más de 2 h.
- **Audio que no convence** → revisar el de U1 antes de generar el resto;
  regenerar solo el archivo afectado.
- **Cambio de examen prioritario** → G6 antes de escribir; el núcleo B1 →
  B2 de U1–U4 se reutiliza.

## Prompt de respaldo

No va en el repo. Ver MVP-01-PLAN-01.

---

*Generado: 5 oct 2026 · Basado en MVP-03-SPEC-01 @ `9aa2e2c` · Estado:
pendiente de aprobación (G0).*
