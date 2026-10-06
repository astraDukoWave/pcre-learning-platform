import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { Link, useParams } from "react-router";
import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { ApiError } from "../../api/errors";
import { Button } from "../../components/Button";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Notice } from "../../components/Notice";
import { Page } from "../../components/Page";
import { ActivityRenderer, isReady } from "../activities/ActivityRenderer";
import { AudioPlayer } from "../activities/audio-player/AudioPlayer";
import type { Activity } from "../lesson/types";
import styles from "./Assessment.module.css";
import { Results } from "./Results";
import type { AssessmentRun } from "./types";

const SUBMIT_KEY = "pcre:submit:";

/** Clave de envío estable por corrida: un reintento tras una falla de red usa la misma. */
function submitKey(runId: string): string {
  try {
    const existing = sessionStorage.getItem(SUBMIT_KEY + runId);
    if (existing) return existing;
    const key = newIdempotencyKey();
    sessionStorage.setItem(SUBMIT_KEY + runId, key);
    return key;
  } catch {
    return newIdempotencyKey();
  }
}

export function RunPage() {
  const { runId = "" } = useParams();
  const query = useQuery({
    queryKey: ["run", runId],
    queryFn: () => unwrap(api.GET("/api/v1/assessment-runs/{run_id}", { params: { path: { run_id: runId } } })),
    retry: false,
  });
  if (query.isPending) return <Page title="Comprobación">Cargando…</Page>;
  if (query.isError) {
    return (
      <Page title="No encontramos esta corrida">
        <ErrorNotice error={query.error} />
        <Link to="/ruta">Ir a la ruta</Link>
      </Page>
    );
  }
  const run = query.data;
  return (
    <Page title={run.form.title} wide>
      <Notice tone="info">{run.label}</Notice>
      <p>
        Corrida {run.run_number}
        {run.comparable ? " · la que se compara" : " · repaso (la comparable es la primera)"}
      </p>
      {run.status === "submitted" ? <Results run={run} /> : <InProgress run={run} />}
    </Page>
  );
}

function InProgress({ run }: { run: AssessmentRun }) {
  const qc = useQueryClient();
  const total = run.items.length;
  const [index, setIndex] = useState(() => {
    const first = run.items.findIndex((i) => !run.answers[i.id]);
    return first === -1 ? total : first;
  });
  const [responses, setResponses] = useState<Record<string, Record<string, unknown>>>(() =>
    Object.fromEntries(Object.entries(run.answers).map(([id, a]) => [id, a.response])),
  );
  const [saved, setSaved] = useState<Set<string>>(() => new Set(Object.keys(run.answers)));
  const [audioFailed, setAudioFailed] = useState<Set<string>>(
    () => new Set(Object.entries(run.answers).filter(([, a]) => a.audio_failed).map(([id]) => id)),
  );
  const [plays, setPlays] = useState(0);

  const save = useMutation({
    mutationFn: (req: { activity: Activity; failed: boolean }) =>
      unwrap(
        api.PUT("/api/v1/assessment-runs/{run_id}/answers/{activity_id}", {
          params: { path: { run_id: run.id, activity_id: req.activity.id } },
          body: { response: req.failed ? {} : (responses[req.activity.id] ?? {}), audio_failed: req.failed },
        }),
      ),
    onSuccess: (_, req) => {
      setSaved((prev) => new Set(prev).add(req.activity.id));
      setAudioFailed((prev) => {
        const next = new Set(prev);
        if (req.failed) next.add(req.activity.id);
        else next.delete(req.activity.id);
        return next;
      });
      setPlays(0);
      setIndex((i) => Math.min(i + 1, total));
    },
  });

  const submit = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/assessment-runs/{run_id}/submit", {
          params: { path: { run_id: run.id }, header: { "Idempotency-Key": submitKey(run.id) } },
        }),
      ),
    onSuccess: (data) => {
      qc.setQueryData(["run", run.id], data);
      void qc.invalidateQueries({ queryKey: ["path"] });
    },
  });

  const onChange = useCallback(
    (activityId: string) => (next: Record<string, unknown>) => setResponses((prev) => ({ ...prev, [activityId]: next })),
    [],
  );
  const onPlay = useCallback(() => setPlays((n) => n + 1), []);

  const activity = run.items[index];
  const passages = run.passages.filter((p) => !activity || activity.stimulus?.passage === p.id);
  const answered = saved.size;

  return (
    <div className={passages.length ? styles.split : undefined}>
      {passages.length ? (
        <section className={styles.passages} aria-label="Texto">
          {passages.map((p) => (
            <article key={p.id} className={styles.passage} lang="en">
              {p.title_en ? <h2>{p.title_en}</h2> : null}
              <p>{p.text_en}</p>
            </article>
          ))}
        </section>
      ) : null}
      <section aria-label="Preguntas">
        <nav aria-label="Preguntas de la comprobación" className={styles.stepper}>
          {run.items.map((a, i) => (
            <button
              key={a.id}
              type="button"
              className={[styles.step, i === index ? styles.current : ""].join(" ")}
              aria-current={i === index ? "step" : undefined}
              onClick={() => setIndex(i)}
            >
              {i + 1}
              {saved.has(a.id) ? <span aria-label=" (guardada)"> ✓</span> : null}
            </button>
          ))}
          <button
            type="button"
            className={[styles.step, index === total ? styles.current : ""].join(" ")}
            onClick={() => setIndex(total)}
          >
            Enviar
          </button>
        </nav>
        {activity ? (
          <article className={styles.card} aria-labelledby={`q-${activity.id}`}>
            <p>
              Pregunta {index + 1} de {total}
            </p>
            <p className={styles.instructions}>{activity.instructions_es}</p>
            <h2 id={`q-${activity.id}`} className={activity.prompt_en ? styles.prompt : "visually-hidden"} lang="en">
              {activity.prompt_en || "Pregunta"}
            </h2>
            {activity.stimulus?.text_en ? (
              <blockquote className={styles.stimulus} lang="en">
                {activity.stimulus.text_en}
              </blockquote>
            ) : null}
            {activity.stimulus?.has_audio ? (
              <>
                <AudioPlayer src={activity.stimulus.audio_url} label="Audio de la pregunta" plays={plays} onPlay={onPlay} />
                {audioFailed.has(activity.id) ? (
                  <Notice tone="info">Marcaste que el audio no cargó: esta pregunta quedará «no evaluable (audio)».</Notice>
                ) : (
                  <Button variant="quiet" onClick={() => save.mutate({ activity, failed: true })}>
                    No pude escuchar el audio
                  </Button>
                )}
              </>
            ) : null}
            <ActivityRenderer
              key={activity.id}
              activity={activity}
              response={responses[activity.id] ?? {}}
              onChange={onChange(activity.id)}
              disabled={save.isPending}
              plays={plays}
              onPlay={onPlay}
            />
            <ErrorNotice error={save.error} />
            <div className={styles.actions}>
              <Button
                onClick={() => save.mutate({ activity, failed: false })}
                busy={save.isPending}
                disabled={!isReady(activity, responses[activity.id] ?? {})}
              >
                {index + 1 < total ? "Guardar y seguir" : "Guardar y revisar"}
              </Button>
            </div>
          </article>
        ) : (
          <article className={styles.card} aria-labelledby="send">
            <h2 id="send">Enviar la comprobación</h2>
            <p>
              Guardaste {answered} de {total} respuestas.
              {answered < total ? " Las preguntas sin respuesta cuentan como no acertadas." : ""}
            </p>
            <p>Al enviar ya no podrás cambiar tus respuestas. Verás tus resultados por objetivo y las explicaciones.</p>
            {submit.error instanceof ApiError && submit.error.isNetwork ? (
              <Notice tone="system-error">No pudimos enviar. Tus respuestas siguen guardadas; vuelve a intentarlo.</Notice>
            ) : (
              <ErrorNotice error={submit.error} />
            )}
            <div className={styles.actions}>
              <Button onClick={() => submit.mutate()} busy={submit.isPending}>
                Enviar comprobación
              </Button>
            </div>
          </article>
        )}
      </section>
    </div>
  );
}
