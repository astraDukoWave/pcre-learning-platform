import { useMutation } from "@tanstack/react-query";
import type React from "react";
import { useEffect, useRef, useState } from "react";
import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { ApiError } from "../../api/errors";
import type { components } from "../../api/schema";
import { Button } from "../../components/Button";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Highlight } from "../../components/Highlight";
import { Notice } from "../../components/Notice";
import { Thumbs } from "../feedback/AiFeedback";
import { reasonText, segments } from "../feedback/aiFeedback";
import feedbackStyles from "../feedback/feedback.module.css";
import styles from "./CoachPage.module.css";

export type VoiceSession = components["schemas"]["VoiceSessionOut"];
type VoiceFeedbackData = components["schemas"]["VoiceFeedbackOut"];
type VoiceObservation = components["schemas"]["VoiceObservationOut"];

const UNAVAILABLE = new Set(["capability_disabled", "budget_exhausted"]);
const VOICE_REASONS: Record<string, string> = {
  too_little_speech: "hablaste menos de 30 segundos; con un poco más de conversación podemos comentarla",
  no_consent: "no marcaste la casilla para guardar la transcripción",
  no_valid_evidence: "el evaluador no pudo citar frases de tus turnos",
};

export function voiceReason(reason: string | null | undefined): string {
  return (reason && VOICE_REASONS[reason]) ?? reasonText(reason);
}

function Observations({ data }: { data: VoiceFeedbackData }) {
  const hidden = data.hidden ?? 0;
  const observations = data.observations ?? [];
  return (
    <>
      <p className={feedbackStyles.caption}>{data.label}</p>
      {observations.length ? (
        <ol className={feedbackStyles.notes}>
          {observations.map((o, i) => (
            <li key={i}>
              <p>
                <strong>{o.criterion_name_es}</strong> · «
                <Highlight>
                  <span lang="en">{o.evidence}</span>
                </Highlight>
                »
              </p>
              <p>{o.observation_es}</p>
              <p>{o.suggestion_es}</p>
              {data.run_id ? <Thumbs runId={data.run_id} index={o.index ?? i} /> : null}
            </li>
          ))}
        </ol>
      ) : null}
      {hidden > 0 ? (
        <p className={feedbackStyles.hint}>
          {hidden === 1 ? "Ocultamos 1 observación" : `Ocultamos ${hidden} observaciones`} sobre turnos que marcaste
          con «Eso no fue lo que dije».
        </p>
      ) : null}
    </>
  );
}

function Transcript({
  session,
  observations,
  disputing,
  onDispute,
  focusTurn,
}: {
  session: VoiceSession;
  observations: VoiceObservation[];
  disputing: boolean;
  onDispute: (n: number) => void;
  /** Turno recién marcado: su aviso recibe el foco (el botón desaparece). */
  focusTurn: React.RefObject<number | null>;
}) {
  const turns = session.transcript ?? [];
  return (
    <details>
      <summary>Transcripción ({turns.length} turnos)</summary>
      <ol className={styles.turns}>
        {turns.map((t) => {
          // Solo se marca la evidencia de las observaciones que citan este turno.
          const parts =
            t.role === "learner"
              ? segments(
                  t.text,
                  observations.map((o) => (o.turn === t.n ? o.evidence : "")),
                )
              : [{ text: t.text, note: null }];
          return (
            <li key={t.n} className={t.role === "coach" ? styles.coach : styles.learner}>
              <span className={styles.who}>{t.role === "coach" ? "Coach" : "Tú"}</span>{" "}
              <span lang="en">
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
              </span>
              {t.aid ? <span className={styles.aid}> (ayuda)</span> : null}
              {t.role === "learner" && !t.aid ? (
                t.disputed ? (
                  <span
                    className={styles.aid}
                    tabIndex={-1}
                    ref={(el) => {
                      if (el && focusTurn.current === t.n) {
                        focusTurn.current = null;
                        el.focus();
                      }
                    }}
                  >
                    {" "}
                    · Marcaste que no fue lo que dijiste
                  </span>
                ) : (
                  <button
                    type="button"
                    className={styles.dispute}
                    disabled={disputing}
                    onClick={() => onDispute(t.n)}
                    aria-label={`Eso no fue lo que dije (turno ${t.n})`}
                  >
                    Eso no fue lo que dije
                  </button>
                )
              ) : null}
            </li>
          );
        })}
      </ol>
    </details>
  );
}

/** Al terminar una práctica de voz (MVP-02 REQ-05 y REQ-06): con el consentimiento de la
 * sesión, se pide el feedback una vez (hasta dos observaciones con evidencia resaltada en su
 * turno); cada turno propio se puede marcar con «Eso no fue lo que dije», que oculta las
 * observaciones que lo citan. Un `failed` se reintenta a mano; un `unknown` no. */
export function VoiceFeedback({
  session,
  onSession,
}: {
  session: VoiceSession;
  onSession: (session: VoiceSession) => void;
}) {
  const [local, setLocal] = useState<VoiceFeedbackData | null>(null);
  // La misma clave en un reintento tras una falla de red; una nueva tras cada resultado.
  const key = useRef<string | null>(null);
  // La sesión se vuelve a leer si al pedir el feedback todavía no tenía la transcripción
  // guardada (p. ej., se perdió la conexión antes de `ended` y el cierre iba detrás).
  const refresh = async () => {
    onSession(
      await unwrap(
        api.GET("/api/v1/voice-sessions/{session_id}", { params: { path: { session_id: session.id } } }),
      ),
    );
  };
  const stale = session.save_transcript && (!session.transcript || session.status === "active");
  const ask = useMutation({
    mutationFn: () => {
      key.current ??= newIdempotencyKey();
      return unwrap(
        api.POST("/api/v1/voice-sessions/{session_id}/feedback", {
          params: { path: { session_id: session.id }, header: { "Idempotency-Key": key.current } },
        }),
      );
    },
    // El cierre de la sesión puede ir un instante detrás del navegador.
    retry: (count, err) => err instanceof ApiError && err.code === "voice_session_open" && count < 5,
    retryDelay: 1000,
    onSuccess: (result) => {
      key.current = null; // un resultado cierra la clave: un `failed` se reintenta con otra
      setLocal(result);
    },
    onSettled: async (result) => {
      if (result?.status === "evaluable" || result?.status === "not_evaluable" || stale) {
        await refresh().catch(() => undefined);
      }
    },
  });
  const focusTurn = useRef<number | null>(null);
  const dispute = useMutation({
    mutationFn: (n: number) =>
      unwrap(
        api.POST("/api/v1/voice-sessions/{session_id}/turns/{n}/flag", {
          params: { path: { session_id: session.id, n } },
        }),
      ),
    onSuccess: (updated, n) => {
      focusTurn.current = n;
      onSession(updated);
    },
  });

  const consent = session.save_transcript;
  const { mutate: requestFeedback } = ask;
  const asked = useRef(false);
  useEffect(() => {
    if (consent && !session.feedback && !asked.current) {
      asked.current = true;
      requestFeedback();
    }
  }, [consent, session.feedback, requestFeedback]);

  const feedback = session.feedback ?? local;
  const error = ask.isPending ? null : ask.error;
  const unavailable = error instanceof ApiError && UNAVAILABLE.has(error.code);
  const inProgress = error instanceof ApiError && error.code === "feedback_in_progress";
  const observations = feedback?.status === "evaluable" ? (feedback.observations ?? []) : [];
  const hidden = feedback?.hidden ?? 0;
  // Se puede volver a pedir tras un `failed` (con otra clave) o tras un error que no es
  // "no disponible" (red, en curso, cierre atrasado: con la misma clave).
  const canRetry =
    consent && !ask.isPending && !unavailable && (feedback?.status === "failed" || (!feedback && !!error));
  const announcement = ask.isPending
    ? "Analizando tu conversación…"
    : feedback?.status === "evaluable"
      ? `Feedback listo: ${observations.length} ${observations.length === 1 ? "observación" : "observaciones"}${
          hidden ? `; ${hidden} oculta${hidden === 1 ? "" : "s"} por turnos marcados` : ""
        }.`
      : feedback?.status === "not_evaluable" && consent
        ? `No pudimos comentar esta conversación: ${voiceReason(feedback.reason)}.`
        : "";

  return (
    <section aria-label="Feedback de la práctica" className={feedbackStyles.ai}>
      {!consent ? (
        <p className={styles.mode}>
          No guardamos la transcripción ni pedimos feedback porque no marcaste la casilla.
        </p>
      ) : null}
      <p className="visually-hidden" role="status" aria-live="polite">
        {announcement}
      </p>
      {ask.isPending ? <p aria-hidden="true">Analizando tu conversación…</p> : null}
      {feedback?.status === "evaluable" ? <Observations data={feedback} /> : null}
      {feedback?.status === "not_evaluable" && consent ? (
        <p>No pudimos comentar esta conversación: {voiceReason(feedback.reason)}.</p>
      ) : null}
      {feedback?.status === "unknown" ? (
        <Notice tone="note">Estamos verificando el feedback de esta práctica; no se volverá a pedir solo.</Notice>
      ) : null}
      {unavailable || feedback?.status === "failed" ? <p>El feedback no está disponible ahora.</p> : null}
      {inProgress ? <p>El feedback sigue en curso. Vuelve a pedirlo en unos segundos.</p> : null}
      {!unavailable && !inProgress ? <ErrorNotice error={error} /> : null}
      {canRetry ? (
        <div className={feedbackStyles.actions}>
          <Button variant="secondary" onClick={() => ask.mutate()}>
            Pedir el feedback otra vez
          </Button>
        </div>
      ) : null}
      {session.transcript ? (
        <Transcript
          session={session}
          observations={observations}
          disputing={dispute.isPending || ask.isPending}
          onDispute={(n) => dispute.mutate(n)}
          focusTurn={focusTurn}
        />
      ) : null}
      <ErrorNotice error={dispute.error} />
    </section>
  );
}
