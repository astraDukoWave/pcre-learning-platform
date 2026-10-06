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
  `expected_status`, `expected_reason`, `must_not_flag` (fragmentos válidos que nunca deben
  señalarse) y `must_mention_criteria`.
- `feedback/recorded/`: salidas **escritas a mano** con la forma de la salida del modelo, para
  probar sin red el validador y el reporte. **No son grabaciones de un modelo real.**
  - `reference/`: un modelo que se porta bien (debe cumplir la regla).
  - `adversarial/`: JSON roto, campos de más, evidencia inventada, URLs y puntajes que el
    validador debe descartar (no cumple la regla por evidencia inválida).
  - `flawed/`: un modelo que señala variantes válidas como errores (no cumple por
    contradicciones).

## Correr

Desde `apps/backend`:

```bash
uv run python ../../evals/run.py --offline reference     # sin red ni llaves
```

El run con modelos reales solo ocurre en `.github/workflows/feedback-eval.yml` (environment
`evals` con aprobación de Jonathan, G5a), con los modelos y sus precios por millón de tokens
como entrada y un tope de costo por run.

## Métricas y regla de selección

- **Contradicciones:** una observación cuya evidencia está dentro de un fragmento de
  `must_not_flag`, o que lo contiene y este ocupa al menos la mitad de sus palabras. Si solo lo
  cita dentro de una frase más larga, se lista como "revisar" (no bloquea).
- **Evidencia válida:** observaciones que pasan el validador entre las devueltas.
- **Abstención**, estado esperado, criterios pedidos, salidas inválidas, latencia p50/p95 y
  costo estimado.
- **Regla:** el modelo más barato con 0 contradicciones, evidencia válida ≥ 95 % y p95 ≤ 12 s.
