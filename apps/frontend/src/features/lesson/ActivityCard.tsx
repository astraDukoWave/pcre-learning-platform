import { useMutation, useQuery } from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";
import { api, unwrap } from "../../api/client";
import { ApiError } from "../../api/errors";
import { Button } from "../../components/Button";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Notice } from "../../components/Notice";
import { ActivityRenderer, isReady } from "../activities/ActivityRenderer";
import { AudioPlayer } from "../activities/audio-player/AudioPlayer";
import styles from "./ActivityCard.module.css";
import { clearDraft, loadDraft, saveDraft } from "./drafts";
import { Feedback } from "./Feedback";
import type { Activity, AttemptDetail, AttemptSummary, ShownResult } from "./types";

const AID_LABELS: Record<string, string> = {
  hint: "Pista",
  support_es: "Apoyo en español",
  transcript: "Transcripción",
  example: "Ejemplo",
};

const PRODUCTIONS = new Set(["short_writing", "recorded_speaking"]);

interface ServedAid {
  kind: string;
  index: number;
  content: string;
}

function fromSummary(last: AttemptSummary | undefined): ShownResult | null {
  if (!last) return null;
  return {
    id: last.id,
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
  const [plays, setPlays] = useState(0);
  const [revisionOf, setRevisionOf] = useState<string | null>(null);
  // Un reintento después de una falla de red reenvía exactamente el mismo cuerpo.
  const pendingBody = useRef<{
    response: string;
    audio_plays: number;
    revision_of: string | null;
  } | null>(null);

  const production = PRODUCTIONS.has(activity.format);
  // Al volver a una producción ya enviada, el intento propio trae la rúbrica y el ejemplo.
  const detail = useQuery({
    queryKey: ["attempt", shown?.id],
    enabled: Boolean(production && shown?.id && !shown.feedback),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/attempts/{attempt_id}", {
          params: { path: { attempt_id: shown?.id ?? "" } },
        }),
      ),
  });
  const view: ShownResult | null =
    shown && !shown.feedback && detail.data
      ? {
          ...shown,
          evaluation_status: detail.data.evaluation_status,
          result: detail.data.result,
          feedback: detail.data.feedback,
        }
      : shown;

  const submit = useMutation({
    mutationFn: () => {
      const draft = saveDraft(activity.id, response);
      const serialized = JSON.stringify(response);
      if (!pendingBody.current || pendingBody.current.response !== serialized) {
        pendingBody.current = {
          response: serialized,
          audio_plays: Math.min(plays, 50),
          revision_of: revisionOf,
        };
      }
      const { audio_plays, revision_of } = pendingBody.current;
      return unwrap(
        api.POST("/api/v1/attempts", {
          params: { header: { "Idempotency-Key": draft.key } },
          body: {
            activity_id: activity.id,
            response,
            audio_plays,
            revision_of,
          },
        }),
      );
    },
    onSuccess: (result) => {
      clearDraft(activity.id);
      pendingBody.current = null;
      setShown({
        id: result.id,
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
      unwrap(
        api.POST("/api/v1/aids", {
          body: { activity_id: activity.id, ...req },
        }),
      ),
    onSuccess: (data) => setAids((prev) => [...prev, data]),
  });

  const update = useCallback(
    (next: Record<string, unknown>) => {
      setResponse(next);
      saveDraft(activity.id, next);
    },
    [activity.id],
  );
  const onPlay = useCallback(() => setPlays((n) => n + 1), []);

  function onAssessed(d: AttemptDetail) {
    setShown((prev) =>
      prev
        ? {
            ...prev,
            evaluation_status: d.evaluation_status,
            result: d.result,
            feedback: d.feedback,
          }
        : prev,
    );
  }

  const answered = view !== null;
  const disabled = answered || submit.isPending;
  const ready = isReady(activity, response);
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
      {activity.stimulus?.has_audio ? (
        <AudioPlayer src={activity.stimulus.audio_url} label="Audio de la actividad" plays={plays} onPlay={onPlay} />
      ) : null}

      {revisionOf && !answered ? (
        <Notice tone="info">Estás reformulando: se guardará como un intento nuevo ligado al anterior.</Notice>
      ) : null}

      <ActivityRenderer
        activity={activity}
        response={response}
        onChange={update}
        disabled={disabled}
        plays={plays}
        onPlay={onPlay}
        result={answered ? view.result : null}
      />

      {!answered && activity.aids.length > 0 ? (
        <div className={styles.aids} role="group" aria-label="Ayudas">
          {activity.aids.map((a) => {
            const used = aids.filter((x) => x.kind === a.kind).length;
            const left = a.count - used;
            if (left <= 0) return null;
            const text =
              a.kind === "hint" && a.count > 1
                ? `${AID_LABELS[a.kind]} (${used + 1} de ${a.count})`
                : AID_LABELS[a.kind];
            return (
              <Button
                key={a.kind}
                variant="secondary"
                busy={aid.isPending}
                onClick={() =>
                  aid.mutate({
                    kind: a.kind,
                    index: a.kind === "hint" ? used : 0,
                  })
                }
              >
                {text}
              </Button>
            );
          })}
        </div>
      ) : null}
      {aids.map((a) => (
        <Notice key={`${a.kind}-${a.index}`} tone="info" title={AID_LABELS[a.kind]}>
          <p lang={a.kind === "transcript" || a.kind === "example" ? "en" : undefined} className={styles.aid}>
            {a.content}
          </p>
        </Notice>
      ))}
      <ErrorNotice error={aid.error} />

      {networkFailed ? (
        <Notice tone="system-error">No pudimos guardar tu respuesta. La conservamos aquí; vuelve a intentarlo.</Notice>
      ) : (
        <ErrorNotice error={submit.error} />
      )}

      {answered ? <Feedback activity={activity} shown={view} onUpdate={onAssessed} /> : null}
      <ErrorNotice error={detail.error} />

      <div className={styles.actions}>
        {!answered ? (
          <Button onClick={() => submit.mutate()} busy={submit.isPending} disabled={!ready}>
            {networkFailed ? "Volver a intentar" : "Enviar respuesta"}
          </Button>
        ) : (
          <>
            {production ? (
              <Button
                variant="quiet"
                onClick={() => {
                  setRevisionOf(view.id ?? null);
                  setShown(null);
                  setAids([]);
                  update(activity.format === "short_writing" ? { text: String(view.response.text ?? "") } : {});
                }}
              >
                {activity.format === "short_writing" ? "Reformular" : "Responder de nuevo"}
              </Button>
            ) : (
              <Button
                variant="quiet"
                onClick={() => {
                  setShown(null);
                  setAids([]);
                  setRevisionOf(null);
                  update({});
                }}
              >
                Intentar de nuevo
              </Button>
            )}
            <Button onClick={onNext}>{isLast ? "Terminar" : "Siguiente actividad"}</Button>
          </>
        )}
      </div>
    </article>
  );
}
