import { useState } from "react";
import { Link } from "react-router";
import { Feedback } from "../lesson/Feedback";
import type { AttemptDetail, ShownResult } from "../lesson/types";
import styles from "./Assessment.module.css";
import { objectiveLabel, type AssessmentRun, type ItemResult } from "./types";

function shownFor(result: ItemResult, response: Record<string, unknown>): ShownResult {
  return {
    id: result.attempt_id ?? undefined,
    correct: result.correct ?? null,
    evaluation_status: result.evaluation_status ?? "",
    result: result.result,
    aided: false,
    explanation: result.feedback.explanation,
    response,
    feedback: result.feedback,
  };
}

/** Resultados por objetivo (aciertos sobre total), explicaciones y ejemplos; la
 * autoevaluación de las producciones es opcional. */
export function Results({ run }: { run: AssessmentRun }) {
  const [overrides, setOverrides] = useState<Record<string, AttemptDetail>>({});
  const summary = run.summary;
  const items = Object.fromEntries(run.items.map((i) => [i.id, i]));
  return (
    <>
      {summary ? (
        <section aria-labelledby="by-objective">
          <h2 id="by-objective">Resultados por objetivo</h2>
          <p>
            Preguntas cerradas: {summary.closed_correct} de {summary.closed_total} correctas.
            {summary.productions_total
              ? ` Producciones respondidas: ${summary.productions_answered} de ${summary.productions_total} (no se califican automáticamente).`
              : ""}
            {summary.not_evaluable_audio ? ` No evaluables por audio: ${summary.not_evaluable_audio}.` : ""}
          </p>
          <table className={styles.table}>
            <caption className="visually-hidden">Aciertos por objetivo</caption>
            <thead>
              <tr>
                <th scope="col">Objetivo</th>
                <th scope="col">Aciertos</th>
              </tr>
            </thead>
            <tbody>
              {summary.objectives.map((o) => (
                <tr key={o.code}>
                  <th scope="row">
                    {objectiveLabel(o.code)} <span className={styles.unit}>({o.code})</span>
                  </th>
                  <td>
                    {o.total ? `${o.correct} de ${o.total}` : "aún sin medición"}
                    {o.not_evaluable ? ` · ${o.not_evaluable} no evaluable (audio)` : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}
      <section aria-labelledby="by-item">
        <h2 id="by-item">Pregunta por pregunta</h2>
        {run.results.map((r, i) => {
          const activity = items[r.activity_id];
          if (!activity) return null;
          const response = run.answers[r.activity_id]?.response ?? {};
          const override = overrides[r.activity_id];
          const shown = shownFor(
            override
              ? { ...r, evaluation_status: override.evaluation_status, result: override.result, feedback: override.feedback }
              : r,
            response,
          );
          return (
            <article key={r.activity_id} className={styles.result} aria-labelledby={`r-${r.activity_id}`}>
              <h3 id={`r-${r.activity_id}`}>
                Pregunta {i + 1}
                {activity.prompt_en ? <span lang="en"> · {activity.prompt_en}</span> : null}
              </h3>
              {!r.answered ? (
                <p className={styles.review}>Sin respuesta.</p>
              ) : r.evaluation_status === "not_evaluable" && r.result.reason === "audio" ? (
                <p>No evaluable (audio): no cuenta en tus resultados.</p>
              ) : null}
              {r.answered && !(r.result.reason === "audio") ? (
                <Feedback
                  activity={activity}
                  shown={shown}
                  onUpdate={(detail) => setOverrides((prev) => ({ ...prev, [r.activity_id]: detail }))}
                />
              ) : r.feedback.explanation ? (
                <p>{r.feedback.explanation}</p>
              ) : null}
            </article>
          );
        })}
      </section>
      <p>
        <Link to="/ruta">Volver a la ruta</Link>
      </p>
    </>
  );
}
