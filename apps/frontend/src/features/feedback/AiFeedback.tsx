import { useMutation } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { ApiError } from "../../api/errors";
import { Button } from "../../components/Button";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Highlight } from "../../components/Highlight";
import { Notice } from "../../components/Notice";
import type { AttemptDetail } from "../lesson/types";
import styles from "./feedback.module.css";
import { type AiFeedback as AiFeedbackData, reasonText, segments } from "./aiFeedback";

const UNAVAILABLE = new Set(["capability_disabled", "budget_exhausted"]);

export function Thumbs({ runId, index }: { runId: string; index: number }) {
  const [sent, setSent] = useState<0 | 1 | null>(null);
  const vote = useMutation({
    mutationFn: (rating: 0 | 1) =>
      unwrap(
        api.POST("/api/v1/feedback", {
          body: { context_type: "ai_observation", context_id: runId, rating, observation: index, message: "" },
        }),
      ).then(() => rating),
    onSuccess: (rating) => setSent(rating),
  });
  return (
    <div className={styles.thumbs} role="group" aria-label={`¿Te sirvió la observación ${index + 1}?`}>
      <button type="button" aria-pressed={sent === 1} disabled={vote.isPending} onClick={() => vote.mutate(1)}>
        <span aria-hidden="true">👍</span> Me sirvió
      </button>
      <button type="button" aria-pressed={sent === 0} disabled={vote.isPending} onClick={() => vote.mutate(0)}>
        <span aria-hidden="true">👎</span> No me sirvió
      </button>
      {sent !== null ? <span role="status">Gracias por decirnos.</span> : null}
    </div>
  );
}

function Result({ data, text }: { data: AiFeedbackData; text: string }) {
  if (data.status === "not_evaluable") {
    return <p>No pudimos evaluar esta respuesta: {reasonText(data.reason)}. Puedes autoevaluarte con la rúbrica.</p>;
  }
  if (data.status === "unknown") {
    return (
      <Notice tone="note">
        Estamos verificando el feedback anterior; no se volverá a pedir solo. Mientras tanto, puedes autoevaluarte.
      </Notice>
    );
  }
  if (data.status === "failed") return null;
  const parts = segments(
    text,
    data.observations.map((o) => o.evidence),
  );
  return (
    <>
      <p className={styles.caption}>{data.label}</p>
      <blockquote lang="en" className={styles.learnerText}>
        {parts.map((p, i) =>
          p.note === null ? (
            <span key={i}>{p.text}</span>
          ) : (
            <Highlight key={i}>
              {p.text}
              <sup aria-label={`observación ${p.note + 1}`}>{p.note + 1}</sup>
            </Highlight>
          ),
        )}
      </blockquote>
      <ol className={styles.notes}>
        {data.observations.map((o, i) => (
          <li key={i}>
            <p>
              <strong>{o.criterion_name_es}</strong> · «<span lang="en">{o.evidence}</span>»
            </p>
            <p>{o.observation_es}</p>
            <p>{o.suggestion_es}</p>
            <Thumbs runId={data.run_id} index={i} />
          </li>
        ))}
      </ol>
    </>
  );
}

/** Feedback abierto con IA sobre el texto del alumno (MVP-02 REQ-02). La autoevaluación con
 * la rúbrica es siempre la alternativa: cuando el feedback no está disponible, falla o se
 * verifica, la alumna puede seguir sin él. */
export function AiFeedback({
  attemptId,
  text,
  stored,
  onSaved,
}: {
  attemptId: string;
  text: string;
  stored: AiFeedbackData | null;
  onSaved: (detail: AttemptDetail) => void;
}) {
  const [data, setData] = useState<AiFeedbackData | null>(stored);
  // La misma clave en un reintento tras una falla de red; una nueva tras cada resultado (un
  // `failed` solo se reintenta con otra clave).
  const key = useRef<string | null>(null);
  const ask = useMutation({
    mutationFn: () => {
      key.current ??= newIdempotencyKey();
      return unwrap(
        api.POST("/api/v1/attempts/{attempt_id}/feedback", {
          params: { path: { attempt_id: attemptId }, header: { "Idempotency-Key": key.current } },
        }),
      );
    },
    onSuccess: async (result) => {
      key.current = null;
      setData(result);
      if (result.status === "evaluable") {
        const detail = await unwrap(
          api.GET("/api/v1/attempts/{attempt_id}", { params: { path: { attempt_id: attemptId } } }),
        );
        onSaved(detail);
      }
    },
  });
  const error = ask.error;
  const unavailable = error instanceof ApiError && UNAVAILABLE.has(error.code);
  const inProgress = error instanceof ApiError && error.code === "feedback_in_progress";
  const canAsk = !data || data.status === "failed";
  return (
    <section className={styles.ai} aria-label="Feedback con IA">
      {data ? <Result data={data} text={text} /> : null}
      {data?.status === "failed" ? (
        <p>El feedback no está disponible ahora. Puedes intentarlo de nuevo o autoevaluarte con la rúbrica.</p>
      ) : null}
      {canAsk && !unavailable ? (
        <Button variant="secondary" busy={ask.isPending} onClick={() => ask.mutate()}>
          {ask.isPending ? "Analizando tu respuesta…" : data ? "Intentar de nuevo" : "Pedir feedback (IA)"}
        </Button>
      ) : null}
      {ask.isPending ? <p role="status">Analizando tu respuesta…</p> : null}
      {unavailable ? (
        <p>El feedback no está disponible ahora. Puedes autoevaluarte con la rúbrica.</p>
      ) : inProgress ? (
        <p>El feedback anterior sigue en curso. Vuelve en unos segundos.</p>
      ) : (
        <ErrorNotice error={error} />
      )}
    </section>
  );
}
