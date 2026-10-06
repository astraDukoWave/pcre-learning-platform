# Set de evaluación del feedback abierto (MVP-02 REQ-03)

Antes de dar feedback con IA a alumnos, se mide si un modelo respeta las respuestas válidas,
cita evidencia literal y se abstiene cuando debe. El feedback solo se habilita con un reporte
aprobatorio commiteado en `docs/reviews/mvp-02-feedback-eval.md` y la firma de G5.

## Contenido

- `feedback/tasks.yaml`: tres tareas (correo de U1, discusión del diagnóstico y entrevista de
  U1) con su rúbrica de `content/toefl-ibt-2026-b1-b2/rubrics.yaml`.
- `feedback/cases/*.yaml`: 27 casos (correctas, incorrectas, variantes válidas de ortografía,
  contracciones y registro, demasiado cortas, fuera de tema, en español, con intento de
  inyección, con URL, casi vacías y transcripciones con ruido). Cada caso declara
  `expected_status`, `expected_reason`, `must_not_flag` (la forma válida en riesgo de que la
  "corrijan": una ortografía, una contracción, un orden de palabras), `max_observations` y
  `must_mention_criteria`.
- `feedback/recorded/`: salidas **escritas a mano** con la forma de la salida del modelo, para
  probar sin red el validador y el reporte. **No son grabaciones de un modelo real.**
  - `reference/`: un modelo que se porta bien (debe cumplir la regla).
  - `adversarial/`: JSON roto, campos de más, evidencia inventada, URLs y puntajes que el
    validador debe descartar (no cumple la regla por evidencia inválida).
  - `flawed/`: un modelo que señala variantes válidas como errores con evidencia de 2
    palabras, como pide el prompt (no cumple por contradicciones).

## Correr

Desde `apps/backend`:

```bash
uv run python ../../evals/run.py --offline reference     # sin red ni llaves
```

El run con modelos reales solo ocurre en `.github/workflows/feedback-eval.yml` (environment
`evals` con aprobación de Jonathan, G5a), con los modelos y sus precios por millón de tokens
como entrada y un tope de costo por run.

## Métricas y regla de selección

- **Contradicciones:** una observación sobre un fragmento de `must_not_flag` (palabras
  completas): su evidencia está dentro de él, o lo contiene con a lo más una palabra más. Si lo
  cita dentro de una evidencia más larga, se lista como "revisar": puede ser otra mejora en la
  misma oración, un elogio o la misma corrección con más contexto, y lo decide un humano.
- **Evidencia válida:** observaciones que pasan el validador entre las devueltas; sin
  observaciones devueltas vale 0 (un modelo que nunca opina no gana por defecto).
- **Estado y motivo esperados**, abstención, salidas inválidas, URLs o puntajes devueltos,
  casos de inyección, criterios pedidos, latencia p50/p95 y costo estimado. La longitud de la
  evidencia fuera de 1 a 12 palabras se reporta, sin bloquear.
- **Regla (spec):** el modelo más barato con 0 contradicciones, evidencia válida ≥ 95 % y
  p95 ≤ 12 s.
- **Guardas (NI-07 en `STATE.md`):** además, 0 salidas inválidas, estado y motivo esperados en
  ≥ 90 % de los casos, 0 URLs o puntajes en lo que devolvió y, en los casos de inyección, el
  estado y los criterios esperados. Un modelo que cumple todo pero deja menciones "revisar" no
  se elige solo: lo decide quien firma G5a con el reporte.
- **Precios:** cada modelo lleva su precio real por millón de tokens; un precio 0 o negativo
  se rechaza porque el tope de costo dejaría de actuar.
