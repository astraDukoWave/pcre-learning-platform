import { useMutation } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { ApiError } from "../../api/errors";
import { Button } from "../../components/Button";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Notice } from "../../components/Notice";
import { recordingFor } from "../activities/recorded-speaking/recordings";
import type { AttemptDetail } from "../lesson/types";
import { AiFeedback } from "./AiFeedback";
import type { AiFeedback as AiFeedbackData } from "./aiFeedback";
import { useCapabilities } from "./capabilities";
import styles from "./feedback.module.css";
import { type StoredTranscription, canTranscribe, sendRecording } from "./transcription";

const UNAVAILABLE = new Set(["capability_disabled", "budget_exhausted"]);

function Repeat({ data }: { data: StoredTranscription }) {
  const repeat = data.repeat;
  if (!repeat) return null;
  return (
    <>
      <p>
        <strong>
          Palabras reconocidas: {repeat.recognized} de {repeat.total}
        </strong>
      </p>
      {repeat.missing.length ? (
        <>
          <p>
            No aparecen: <span lang="en">{repeat.missing.join(", ")}</span>
          </p>
          {data.hint_es ? <p>{data.hint_es}</p> : null}
        </>
      ) : (
        <p>Se reconocieron todas las palabras de la oración.</p>
      )}
      <p className={styles.caption}>Es una guía del reconocimiento de voz, no una calificación.</p>
    </>
  );
}

function Interview({
  attemptId,
  data,
  aiFeedback,
  onSaved,
}: {
  attemptId: string;
  data: StoredTranscription;
  aiFeedback: AiFeedbackData | null;
  onSaved: (detail: AttemptDetail) => void;
}) {
  const decide = useMutation({
    mutationFn: (confirmed: boolean) =>
      unwrap(
        api.POST("/api/v1/attempts/{attempt_id}/transcription", {
          params: { path: { attempt_id: attemptId } },
          body: { confirmed },
        }),
      ),
    onSuccess: onSaved,
  });
  const text = data.text ?? "";
  return (
    <>
      <p>
        <strong>Esto entendimos:</strong>
      </p>
      <blockquote lang="en" className={styles.learnerText}>
        {text || "—"}
      </blockquote>
      {data.confirmed ? (
        <AiFeedback attemptId={attemptId} text={text} stored={aiFeedback} onSaved={onSaved} />
      ) : (
        <>
          {data.disputed ? (
            <p>Marcaste que no es lo que dijiste: no pediremos feedback sobre este texto.</p>
          ) : (
            <p>¿Es lo que dijiste? Solo pedimos feedback sobre una transcripción que confirmes.</p>
          )}
          <div className={styles.actions}>
            <Button variant="secondary" busy={decide.isPending} onClick={() => decide.mutate(true)}>
              {data.disputed ? "La revisé: sí es lo que dije" : "Sí, es lo que dije"}
            </Button>
            {!data.disputed ? (
              <Button variant="quiet" disabled={decide.isPending} onClick={() => decide.mutate(false)}>
                Eso no fue lo que dije
              </Button>
            ) : null}
          </div>
          <ErrorNotice error={decide.error} />
        </>
      )}
    </>
  );
}

/** Transcripción de la grabación (MVP-02 REQ-04). Solo se envía si la alumna la pide y si
 * la grabación sigue en esta página; sin transcripción, la autoevaluación sigue disponible. */
export function Transcription({
  attemptId,
  activityId,
  stored,
  aiFeedback,
  onSaved,
}: {
  attemptId: string;
  activityId: string;
  stored: StoredTranscription | null;
  aiFeedback: AiFeedbackData | null;
  onSaved: (detail: AttemptDetail) => void;
}) {
  const capabilities = useCapabilities();
  const [fresh, setFresh] = useState<StoredTranscription | null>(null);
  // La misma clave si se reintenta tras una falla de red; una nueva tras cada resultado.
  const key = useRef<string | null>(null);
  const recording = recordingFor(activityId);
  const send = useMutation({
    mutationFn: () => {
      if (!recording) throw new Error("sin grabación");
      key.current ??= newIdempotencyKey();
      return sendRecording(attemptId, activityId, recording, key.current);
    },
    onSuccess: (result) => {
      key.current = null;
      setFresh(result);
    },
  });
  // Lo guardado en el intento manda (trae la confirmación o la disputa); si no, lo recién pedido.
  const data = stored ?? fresh;
  const error = send.error;
  const unavailable = (error instanceof ApiError && UNAVAILABLE.has(error.code)) || capabilities.data?.stt === false;

  if (data?.status === "transcribed") {
    return (
      <section className={styles.ai} aria-label="Transcripción">
        {data.kind === "repeat" ? (
          <Repeat data={data} />
        ) : (
          <Interview attemptId={attemptId} data={data} aiFeedback={aiFeedback} onSaved={onSaved} />
        )}
      </section>
    );
  }
  if (!recording && !data) return null;
  if (unavailable) {
    return recording ? (
      <p className={styles.caption}>La transcripción automática no está disponible ahora. Autoevalúate con la rúbrica.</p>
    ) : null;
  }
  const tooLong = recording !== null && !canTranscribe(recording);
  return (
    <section className={styles.ai} aria-label="Transcripción">
      {data?.status === "unknown" ? (
        <Notice tone="note">
          Estamos verificando la transcripción anterior; no se volverá a pedir sola. Mientras tanto, autoevalúate.
        </Notice>
      ) : null}
      {data?.status === "failed" ? <p>No se pudo transcribir esta vez. Puedes intentarlo de nuevo.</p> : null}
      {recording && (!data || data.status === "failed") ? (
        tooLong ? (
          <p className={styles.caption}>La transcripción admite grabaciones de hasta 60 segundos.</p>
        ) : (
          <>
            <Button variant="secondary" busy={send.isPending} onClick={() => send.mutate()}>
              {send.isPending ? "Transcribiendo…" : data ? "Intentar de nuevo" : "Transcribir mi grabación"}
            </Button>
            <p className={styles.caption}>
              Se envía a un servicio de reconocimiento de voz (Deepgram) solo para transcribirla; el audio no se guarda.
            </p>
          </>
        )
      ) : null}
      {send.isPending ? <p role="status">Transcribiendo tu grabación…</p> : null}
      {error instanceof ApiError && error.code === "transcription_in_progress" ? (
        <p>La transcripción anterior sigue en curso. Vuelve en unos segundos.</p>
      ) : (
        <ErrorNotice error={error} />
      )}
    </section>
  );
}
