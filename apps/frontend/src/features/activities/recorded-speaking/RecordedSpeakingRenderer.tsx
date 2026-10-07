import { useCallback, useEffect } from "react";
import { Button } from "../../../components/Button";
import { Notice } from "../../../components/Notice";
import type { RecordedSpeakingData } from "../../lesson/types";
import { AudioPlayer } from "../audio-player/AudioPlayer";
import { keepRecording } from "./recordings";
import styles from "./RecordedSpeakingRenderer.module.css";
import { useRecorder } from "./useRecorder";

export interface RecordedSpeakingRendererProps {
  activityId: string;
  data: RecordedSpeakingData;
  response: Record<string, unknown>;
  onChange: (response: Record<string, unknown>) => void;
  disabled: boolean;
  plays: number;
  onPlay: () => void;
}

/** Entrevista o repetición: graba hasta `response_seconds` y reproduce localmente. La
 * grabación solo sale del equipo si, después de enviar, la alumna pide la transcripción.
 * Si el micrófono no está disponible, se puede continuar sin grabar (no evaluable). */
export function RecordedSpeakingRenderer({
  activityId,
  data,
  response,
  onChange,
  disabled,
  plays,
  onPlay,
}: RecordedSpeakingRendererProps) {
  const remember = useCallback(
    (blob: Blob, durationMs: number) => keepRecording(activityId, { blob, durationMs }),
    [activityId],
  );
  const rec = useRecorder(data.response_seconds, data.prep_seconds ?? 0, remember);
  const recorded = rec.state === "recorded";

  useEffect(() => {
    if (recorded && response.recorded !== true) onChange({ recorded: true });
  }, [recorded, response.recorded, onChange]);

  const blocked = rec.state === "denied" || rec.state === "unsupported" || rec.state === "failed";

  return (
    <div className={styles.wrap}>
      {data.subtype === "listen_and_repeat" ? (
        <>
          <p className={styles.step}>1. Escucha el modelo.</p>
          <AudioPlayer src={data.audio_url} label="Oración modelo" plays={plays} onPlay={onPlay} />
          <p className={styles.step}>2. Grábate repitiéndola.</p>
        </>
      ) : (
        <blockquote className={styles.question} lang="en">
          {data.question_en}
        </blockquote>
      )}
      <p className={styles.privacy}>
        Tu grabación se queda en tu dispositivo. Solo si después pides la transcripción, se envía a un servicio de
        reconocimiento de voz y no se guarda.
      </p>
      <p className={styles.limits}>
        {data.prep_seconds ? `${data.prep_seconds} s para preparar · ` : ""}
        hasta {data.response_seconds} s para responder
      </p>

      {rec.state === "preparing" ? (
        <p className={styles.timer} aria-live="polite">
          Prepárate: empiezas a grabar en {rec.secondsLeft} s.{" "}
          <Button variant="quiet" onClick={() => void rec.record()}>
            Grabar ya
          </Button>
        </p>
      ) : null}
      {rec.state === "recording" ? (
        <p className={styles.timer} aria-live="polite">
          <span className={styles.dot} aria-hidden="true" /> Grabando · quedan {rec.secondsLeft} s
        </p>
      ) : null}
      {rec.state === "requesting" ? <p aria-live="polite">Pidiendo acceso al micrófono…</p> : null}

      {blocked ? (
        <Notice tone="system-error" title="No pude grabar">
          {rec.state === "denied" ? (
            <p>
              El navegador no tiene permiso para usar el micrófono. Puedes darlo en la configuración del sitio (el
              candado junto a la dirección) y volver a intentar, o continuar sin grabar.
            </p>
          ) : rec.state === "unsupported" ? (
            <p>Este navegador no permite grabar audio. Puedes continuar sin grabar.</p>
          ) : (
            <p>No encontramos un micrófono que funcione. Revisa que esté conectado o continúa sin grabar.</p>
          )}
          <p>Sin grabación, la actividad queda como «no evaluable»; igual verás el ejemplo.</p>
        </Notice>
      ) : null}

      {rec.url ? (
        <div className={styles.playback}>
          <p className={styles.step}>Tu grabación:</p>
          <audio src={rec.url} controls aria-label="Tu grabación">
            <track kind="captions" />
          </audio>
        </div>
      ) : null}

      {!disabled ? (
        <div className={styles.controls}>
          {rec.state === "recording" ? (
            <Button onClick={rec.stop}>Detener</Button>
          ) : rec.state !== "preparing" && rec.state !== "requesting" && rec.state !== "unsupported" ? (
            <Button variant={recorded ? "secondary" : "primary"} onClick={rec.start}>
              {recorded ? "Grabar otra vez" : blocked ? "Intentar de nuevo" : "Grabar"}
            </Button>
          ) : null}
          {blocked && response.recorded !== false ? (
            <Button variant="secondary" onClick={() => onChange({ recorded: false })}>
              Continuar sin grabar
            </Button>
          ) : null}
          {response.recorded === false ? <p>Enviarás sin grabación.</p> : null}
        </div>
      ) : null}
    </div>
  );
}
