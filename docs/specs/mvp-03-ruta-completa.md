# Spec: mvp-03-ruta-completa

spec_id: MVP-03-SPEC-01
Ciclo SDD MVP-03 · Lane: Standard. Publicar y generar audio conservan su
gate (ver "Riesgo por acción").
Estado: **PENDIENTE DE APROBACIÓN** (gate G0). Arranca solo con el gate
**G6** (ver "Supuestos y decisiones abiertas").
Base: el `main` que dejen MVP-01 y MVP-02. Contenido:
`docs/contenido/contrato-curricular.md` v1.0 (todo el documento).
Skills aplicadas: `design-spec` v0.2. `system-design-spec` no aplica: el
ciclo no toca datos, APIs ni escala, salvo la vista comparativa (REQ-05),
que solo lee tablas existentes.

---

## Resumen general

MVP-01 deja publicada (tras la revisión de Jonathan) la Unidad 1 con el
diagnóstico inicial; MVP-02 agrega el coach y el feedback con IA. Este
ciclo completa la primera ruta: las unidades 2 a 8 (28 lecciones), siete
escenarios, siete checkpoints, el formulario final y el audio de todo lo
que se escucha. Además, una vista que compara el diagnóstico inicial con el
final por objetivo, siempre como evidencia formativa.

El trabajo es sobre todo editorial. El agente redacta y verifica; Jonathan
revisa y publica por lotes (una unidad por lote). La ruta se marca
"completa" sola, cuando cumple el contrato curricular §10, nunca a mano.

## Objetivos del usuario

1. Como alumna, quiero seguir de la Unidad 1 a la 8 con dificultad
   creciente y menos apoyo, sin huecos en las tareas que voy a encontrar.
2. Como alumna, quiero comparar al final mi diagnóstico inicial con el
   final por objetivo, sin que eso se presente como una certificación.
3. Como responsable editorial, quiero revisar cada unidad en un paquete
   ordenado y publicarla cuando la apruebe, sin frenar a quien ya está
   practicando.

## Alcance estricto v1

### Incluye

- Guía de estilo derivada de la revisión de U1 (REQ-01).
- Unidades 2–8 completas según los mínimos y las familias del contrato.
- Escenarios U2–U8 en sus dos modos (texto y voz).
- Checkpoints U2–U8 y formulario final.
- Guiones de audio, manifiesto y solicitud de generación por unidad.
- Cobertura completa y cálculo automático de "ruta completa".
- Vista comparativa inicial vs. final.
- Paquetes de revisión por unidad para Jonathan.

### NO incluye

- Otras rutas, exámenes o niveles (B2 → C1 queda para después).
- Cambios de producto que salgan del feedback del piloto: entran como
  enmiendas o como un ciclo nuevo.
- Retiro de las tablas legadas (ciclo propio).
- Publicar sin la aprobación de Jonathan.

## Requisitos

### Funcionales

- **REQ-01 · Guía de estilo.** Antes de escribir U2, el agente convierte
  los hallazgos de la revisión de U1 (`review_findings`, comentarios de
  Jonathan y valoraciones del piloto) en reglas concretas en
  `docs/contenido/guia-de-estilo.md` (versionada). Cada regla cita el
  hallazgo que la originó. Toda unidad nueva la cumple; el lint aplica las
  reglas que se pueden automatizar.
- **REQ-02 · Unidades 2–8.** Cuatro lecciones por unidad que cumplen el
  contrato §4–§6: objetivos del mapa, familias mínimas, extensiones por
  nivel y apoyo en español que se reduce en U5–U7 y desaparece en U8. Todo
  original, con fuentes registradas.
- **REQ-03 · Escenarios U2–U8.** Un escenario por unidad (contrato §7) con
  grafo determinista para el modo texto y configuración del coach para el
  modo voz.
- **REQ-04 · Checkpoints U2–U8.** Al menos 6 ítems cerrados del pool
  `assessment` y una producción breve, con ítems nuevos.
- **REQ-05 · Formulario final y comparación.**
  - Formulario final con el mismo reparto de objetivos que el inicial (12
    cerrados, 2 escritas, 2 orales), sin ítems compartidos con el inicial
    ni con la práctica.
  - Vista de resultados "Inicial y final": aciertos por objetivo en ambos
    formularios y las producciones de ambos lado a lado (con su
    evaluación, si la hubo). Texto fijo: "Esta comparación es formativa:
    muestra cómo respondiste dos formularios parecidos. No es una
    certificación ni una puntuación oficial."
  - Disponible cuando el alumno completa el formulario final; el final se
    sugiere al completar al menos 6 de las 8 unidades.
- **REQ-06 · Audio.** Guion y entrada de manifiesto para cada actividad de
  escucha y de repetición. Una ejecución de `content-audio.yml` por unidad
  (G2), con el costo estimado en la solicitud. La revisión del audio la
  marca Jonathan (`reviewed_by`).
- **REQ-07 · Cobertura y ruta completa.**
  - `cobertura.md` sin "pendiente" en contenido ni en familias.
  - El sistema calcula `route_complete` (contrato §10): todo publicado,
    cada familia en práctica y en una comprobación posterior y todo audio
    revisado. Se muestra en el panel del admin y, solo cuando es verdadero,
    al alumno ("Ruta inicial completa").
- **REQ-08 · Paquetes de revisión.** `make review-packet UNIT=u2` (la
  herramienta nace en MVP-01 para revisar U1) genera
  `docs/contenido/revision/u2.md` con: ítems y objetivos, resumen de
  claves y variantes, fuentes por afirmación, advertencias del lint,
  guiones de audio y la lista de revisión del contrato §12. Se regenera con
  cada cambio y la CI comprueba que esté al día.

### No funcionales

- **NFR-01 · Calidad.** Lint y cobertura sin errores; ningún marcador
  pendiente; ninguna regla absoluta sin la confirmación del revisor.
- **NFR-02 · Progresión.** Las extensiones y la proporción de apoyo en
  español por unidad siguen el contrato §6.2 y §4 (el lint lo reporta por
  unidad).
- **NFR-03 · Rendimiento.** Con 8 unidades, los endpoints del catálogo y de
  la lección siguen dentro de NFR-03 de MVP-01 (se repite el smoke).
- **NFR-04 · Accesibilidad.** Transcripción disponible para todo audio, con
  las reglas de práctica y comprobación del contrato §11.

## Comportamiento esperado

### Flujo feliz

1. El agente publica la guía de estilo y escribe U2 completa. El lint y la
   cobertura pasan y se genera `revision/u2.md`.
2. Pide la generación del audio de U2 (Jonathan aprueba el run de
   `content-audio.yml` y revisa el PR con los MP3).
3. Jonathan abre el paquete de U2, revisa en el panel, registra hallazgos;
   el agente los corrige en una revisión nueva; Jonathan aprueba y publica
   la unidad.
4. Las alumnas ven U2 en la ruta mientras U3 está en revisión.
5. Con U8 publicada y la cobertura completa, el panel muestra "ruta
   completa" y las alumnas reciben la invitación al formulario final.

### Casos edge

- **EDGE-01 · Una unidad tiene hallazgos que cambian una regla de la
  guía.** Enmienda de la guía con su origen; las unidades ya escritas se
  revisan contra la regla nueva.
- **EDGE-02 · Un objetivo no logra suficientes ítems de calidad.** La
  cobertura lo marca pendiente y el ciclo no se declara terminado; no se
  rellena.
- **EDGE-03 · El audio generado suena mal o no coincide con el guion.**
  Jonathan no lo marca como revisado; se ajusta el guion o la voz y se
  vuelve a generar solo ese archivo.
- **EDGE-04 · Una alumna está a mitad de una unidad cuando se publica una
  revisión.** Revisión fijada, como en MVP-01.
- **EDGE-05 · La alumna hace el formulario final sin haber hecho el
  inicial.** La vista comparativa muestra solo el final y explica por qué.

## Manejo de errores

| Situación | Qué ve el usuario | Qué se registra |
|---|---|---|
| Unidad sin publicar | No aparece en la ruta | — |
| Audio pendiente de revisión | La actividad no se publica (no llega al alumno) | Advertencia del lint en el paquete de revisión |
| Formulario final sin formulario inicial | "Aún no hiciste el diagnóstico inicial; aquí está tu resultado del final." | info |

## Supuestos y decisiones abiertas

- **Gate G6 · Arranque de MVP-03.** Requiere: (a) que Jonathan haya
  revisado U1 (aprobada o con hallazgos registrados) y (b) que haya
  confirmado si los primeros clientes necesitan TOEFL iBT u otro examen
  (pregunta 2 de G0). Si la respuesta cambia la ruta prioritaria, este spec
  se enmienda antes de escribir U2. Dueño: Jonathan.
- `[supuesto]` Una unidad por lote y una semana por lote es un ritmo
  sostenible de revisión. Se mide con el tiempo editorial de MVP-01.
- `[supuesto]` Las voces de Aura-2 son suficientes para la comprensión
  auditiva B1–B2; se valida al revisar el audio de U1.

## Riesgo por acción

| Acción propuesta | Clase | Gate que la cubre |
|---|---|---|
| Escribir contenido, guiones y paquetes en ramas con PR | Rutina | `ci-gate` |
| Mergear contenido en borrador | Rutina con la delegación de G0 (no llega a alumnos sin publicar) | `ci-gate` + G0 |
| Generar audio con TTS (una vez por unidad) | Alto (dinero, acotado: ~USD 1 por unidad) | G2 por run |
| Publicar cada unidad | Alto (impacto educativo) | G3 por unidad |

## Release, rollback y evidencia

- Una rama y un PR por unidad (contenido + guiones + paquete).
- Evidencia: lint, cobertura, paquete de revisión, prueba de la vista
  comparativa y prueba de `route_complete`.
- Rollback editorial: retirar o republicar la revisión anterior.

## Métricas de resultado

| Métrica | Fuente | Baseline | Review | Decisión |
|---|---|---|---|---|
| Avance en la ruta por alumno | `lesson_progress` | Unidades completadas al inicio de MVP-03 | Cada 2 semanas | Informativa |
| Valoración por unidad | `user_feedback` | Media de U1 | Al publicar cada unidad | < 3 → revisar antes de la siguiente |
| Reportes por unidad | `content_reports` | Tasa de U1 | Al publicar cada unidad | > 2 por 100 intentos → revisar el lote |
| Tiempo editorial por unidad | Notas de aprobación | Tiempo de U1 | Por unidad | > 2 h → priorizar revisión asistida (LB-04) |
| Comparación inicial vs. final por objetivo | `assessment_runs` | Diagnóstico inicial | Al completar el final | Solo descriptiva |

## Archivos afectados (estimación, no contrato)

- `content/toefl-ibt-2026-b1-b2/units/u2…u8/`, `assessments/final.yaml`,
  `audio/manifest.yaml`.
- `docs/contenido/guia-de-estilo.md`, `docs/contenido/revision/u2…u8.md`,
  `docs/contenido/cobertura.md`.
- Backend: cálculo de `route_complete` y endpoint de comparación en
  `practice`/`progress`; frontend: vista "Inicial y final".
- `Makefile` (`review-packet`), `HANDOFF.md`, `STATE.md`,
  `docs/reviews/mvp-03-verify.md`.

## Definition of Done

Del agente:

- [ ] **AC-01** — Lint y cobertura sin errores con 32 lecciones, 8
  escenarios, 8 checkpoints y 2 formularios; cada familia en práctica y en
  una comprobación posterior; ningún objetivo pendiente (salvo audio en
  revisión humana).
- [ ] **AC-02** — Formularios inicial y final disjuntos y con el mismo
  reparto de objetivos (prueba).
- [ ] **AC-03** — Ningún apoyo en español en U8 ni en ítems de
  comprobación (lint).
- [ ] **AC-04** — Guion y manifiesto para todo audio; un run de
  `content-audio.yml` solicitado por unidad (estado de cada uno en
  `STATE.md`).
- [ ] **AC-05** — La vista "Inicial y final" muestra los datos de un
  fixture, con el texto formativo fijo.
- [ ] **AC-06** — `route_complete` es verdadero solo con todo publicado,
  cobertura completa y audio revisado (pruebas con fixtures que fallan
  cada condición por separado).
- [ ] **AC-07** — Paquetes de revisión de U2–U8 generados y al día.
- [ ] **AC-08** — `docs/reviews/mvp-03-verify.md`, `HANDOFF.md` y
  `STATE.md` al día.

De Jonathan (M2 terminado, fuera del DoD del agente):

- [ ] **AC-09** — U2–U8 revisadas, con audio revisado y publicadas; el
  panel muestra `route_complete`.

---

## Enmiendas

Ninguna todavía.
