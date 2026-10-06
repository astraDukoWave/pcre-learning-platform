import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { api, unwrap } from "../../api/client";
import { Button } from "../../components/Button";
import { ErrorNotice } from "../../components/ErrorNotice";
import styles from "./SelfAssessment.module.css";
import type { AttemptDetail, Rubric } from "./types";

/** Autoevaluación guiada (REQ-10, contrato §8): después de enviar, el alumno marca cada
 * criterio de 0 a 3; luego ve el ejemplo comentado. Se guarda como `self`. */
export function SelfAssessment({
  attemptId,
  rubric,
  onSaved,
}: {
  attemptId: string;
  rubric: Rubric;
  onSaved: (detail: AttemptDetail) => void;
}) {
  const [scores, setScores] = useState<Record<string, number>>({});
  const save = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/attempts/{attempt_id}/self-assessment", {
          params: { path: { attempt_id: attemptId } },
          body: { scores },
        }),
      ),
    onSuccess: onSaved,
  });
  const complete = rubric.criteria.every((c) => scores[c.id] !== undefined);
  return (
    <section className={styles.wrap} aria-labelledby={`sa-${attemptId}`}>
      <h3 id={`sa-${attemptId}`}>Autoevalúa tu respuesta</h3>
      <p>
        Rúbrica «{rubric.name_es}» (versión {rubric.version}). Marca el nivel que mejor describe lo que hiciste; después
        verás el ejemplo comentado.
      </p>
      {rubric.note_es ? <p className={styles.note}>{rubric.note_es}</p> : null}
      {rubric.criteria.map((c) => (
        <fieldset key={c.id} className={styles.criterion}>
          <legend>{c.name_es}</legend>
          {c.levels.map((level) => (
            <label key={level.score} className={styles.level}>
              <input
                type="radio"
                name={`${attemptId}-${c.id}`}
                value={level.score}
                checked={scores[c.id] === level.score}
                onChange={() => setScores((prev) => ({ ...prev, [c.id]: level.score }))}
              />
              <span>
                <strong>{level.score}</strong> · {level.descriptor_es}
              </span>
            </label>
          ))}
        </fieldset>
      ))}
      <ErrorNotice error={save.error} />
      <Button onClick={() => save.mutate()} busy={save.isPending} disabled={!complete}>
        Guardar autoevaluación
      </Button>
    </section>
  );
}
