import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { api, unwrap } from "../../api/client";
import { ApiError } from "../../api/errors";
import { Button } from "../../components/Button";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Notice } from "../../components/Notice";
import { ChoiceRenderer } from "../activities/choice/ChoiceRenderer";
import styles from "./ActivityCard.module.css";
import { clearDraft, loadDraft, saveDraft } from "./drafts";
import { Feedback } from "./Feedback";
import type { Activity, AttemptSummary, ChoiceData, ShownResult } from "./types";

const AID_LABELS: Record<string, string> = {
  hint: "Pista",
  support_es: "Apoyo en español",
  transcript: "Transcripción",
  example: "Ejemplo",
};

interface ServedAid {
  kind: string;
  index: number;
  content: string;
}

function fromSummary(last: AttemptSummary | undefined): ShownResult | null {
  if (!last) return null;
  return {
    correct: last.correct ?? null,
    evaluation_status: last.evaluation_status,
    result: last.result,
    aided: last.aided,
    response: last.response,
  };
}

export function ActivityCard({
  activity,
  last,
  onSubmitted,
  onNext,
  isLast,
}: {
  activity: Activity;
  last?: AttemptSummary;
  onSubmitted: (lessonCompleted: boolean | null | undefined) => void;
  onNext: () => void;
  isLast: boolean;
}) {
  const initial = loadDraft(activity.id)?.response ?? last?.response ?? {};
  const [response, setResponse] = useState<Record<string, unknown>>(initial);
  const [shown, setShown] = useState<ShownResult | null>(() => (loadDraft(activity.id) ? null : fromSummary(last)));
  const [aids, setAids] = useState<ServedAid[]>([]);

  const submit = useMutation({
    mutationFn: () => {
      const draft = saveDraft(activity.id, response);
      return unwrap(
        api.POST("/api/v1/attempts", {
          params: { header: { "Idempotency-Key": draft.key } },
          body: { activity_id: activity.id, response, audio_plays: 0 },
        }),
      );
    },
    onSuccess: (result) => {
      clearDraft(activity.id);
      setShown({
        correct: result.correct ?? null,
        evaluation_status: result.evaluation_status,
        result: result.result,
        aided: result.aided,
        explanation: result.feedback.explanation,
        response,
        feedback: result.feedback,
      });
      onSubmitted(result.lesson_completed);
    },
  });

  const aid = useMutation({
    mutationFn: (req: { kind: "hint" | "support_es" | "transcript" | "example"; index: number }) =>
      unwrap(api.POST("/api/v1/aids", { body: { activity_id: activity.id, ...req } })),
    onSuccess: (data) => setAids((prev) => [...prev, data]),
  });

  function update(next: Record<string, unknown>) {
    setResponse(next);
    saveDraft(activity.id, next);
  }

  const answered = shown !== null;
  const selected = (response.selected as string[] | undefined) ?? [];
  const correctOptions = answered ? ((shown.result.correct_options as string[] | undefined) ?? null) : null;
  const ready = activity.format === "choice" ? selected.length > 0 : Object.keys(response).length > 0;
  const networkFailed = submit.error instanceof ApiError && submit.error.isNetwork;

  return (
    <article className={styles.card} aria-labelledby={`act-${activity.id}`}>
      <p className={styles.instructions}>{activity.instructions_es}</p>
      {activity.prompt_en ? (
        <h2 id={`act-${activity.id}`} className={styles.prompt} lang="en">
          {activity.prompt_en}
        </h2>
      ) : (
        <h2 id={`act-${activity.id}`} className="visually-hidden">
          Actividad
        </h2>
      )}
      {activity.stimulus?.text_en ? (
        <blockquote className={styles.stimulus} lang="en">
          {activity.stimulus.text_en}
        </blockquote>
      ) : null}

      {activity.format === "choice" ? (
        <ChoiceRenderer
          activityId={activity.id}
          data={activity.data as unknown as ChoiceData}
          selected={selected}
          onChange={(next) => update({ selected: next })}
          disabled={answered || submit.isPending}
          correctOptions={correctOptions}
          legend={activity.prompt_en || activity.instructions_es}
        />
      ) : (
        <Notice tone="info">Este formato llega en la siguiente versión.</Notice>
      )}

      {!answered && activity.aids.length > 0 ? (
        <div className={styles.aids} role="group" aria-label="Ayudas">
          {activity.aids.map((a) => {
            const used = aids.filter((x) => x.kind === a.kind).length;
            const left = a.count - used;
            if (left <= 0) return null;
            const label = a.kind === "hint" && a.count > 1 ? `${AID_LABELS[a.kind]} (${used + 1} de ${a.count})` : AID_LABELS[a.kind];
            return (
              <Button
                key={a.kind}
                variant="secondary"
                busy={aid.isPending}
                onClick={() => aid.mutate({ kind: a.kind, index: a.kind === "hint" ? used : 0 })}
              >
                {label}
              </Button>
            );
          })}
        </div>
      ) : null}
      {aids.map((a) => (
        <Notice key={`${a.kind}-${a.index}`} tone="info" title={AID_LABELS[a.kind]}>
          <p>{a.content}</p>
        </Notice>
      ))}
      <ErrorNotice error={aid.error} />

      {networkFailed ? (
        <Notice tone="system-error">No pudimos guardar tu respuesta. La conservamos aquí; vuelve a intentarlo.</Notice>
      ) : (
        <ErrorNotice error={submit.error} />
      )}

      {answered ? <Feedback activity={activity} shown={shown} /> : null}

      <div className={styles.actions}>
        {!answered ? (
          <Button onClick={() => submit.mutate()} busy={submit.isPending} disabled={!ready}>
            {networkFailed ? "Volver a intentar" : "Enviar respuesta"}
          </Button>
        ) : (
          <>
            <Button
              variant="quiet"
              onClick={() => {
                setShown(null);
                setAids([]);
                update({});
              }}
            >
              Intentar de nuevo
            </Button>
            <Button onClick={onNext}>{isLast ? "Terminar la lección" : "Siguiente actividad"}</Button>
          </>
        )}
      </div>
    </article>
  );
}
