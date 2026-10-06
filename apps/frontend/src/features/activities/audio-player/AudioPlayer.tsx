import { useRef, useState } from "react";
import { Button } from "../../../components/Button";
import { Notice } from "../../../components/Notice";
import styles from "./AudioPlayer.module.css";

export interface AudioPlayerProps {
  src: string | null | undefined;
  label: string;
  plays: number;
  onPlay: () => void;
}

/** Reproductor nativo (operable con teclado) con conteo de reproducciones y reintento. La
 * transcripción no está aquí: es una ayuda que sirve el servidor y queda registrada. */
export function AudioPlayer({ src, label, plays, onPlay }: AudioPlayerProps) {
  const ref = useRef<HTMLAudioElement>(null);
  const fresh = useRef(true);
  const [failures, setFailures] = useState(0);
  const [failed, setFailed] = useState(false);

  if (!src) {
    return <Notice tone="info">El audio de esta actividad todavía no está disponible.</Notice>;
  }

  return (
    <div className={styles.player}>
      <audio
        ref={ref}
        src={src}
        controls
        preload="metadata"
        aria-label={label}
        onPlay={() => {
          if (fresh.current) onPlay();
          fresh.current = false;
        }}
        onEnded={() => {
          fresh.current = true;
        }}
        onCanPlay={() => setFailed(false)}
        onError={() => {
          setFailed(true);
          setFailures((n) => n + 1);
        }}
      >
        <track kind="captions" />
      </audio>
      <p className={styles.meta} aria-live="polite">
        {plays === 0 ? "Aún no lo escuchas." : plays === 1 ? "Lo escuchaste 1 vez." : `Lo escuchaste ${plays} veces.`}
      </p>
      {failed ? (
        <Notice tone="system-error" title="No pudimos cargar el audio">
          {failures >= 2 ? (
            <p>Si sigue sin cargar, pide la transcripción: queda registrada como ayuda.</p>
          ) : (
            <p>Revisa tu conexión y vuelve a intentarlo.</p>
          )}
          <Button
            variant="secondary"
            onClick={() => {
              setFailed(false);
              ref.current?.load();
            }}
          >
            Reintentar el audio
          </Button>
        </Notice>
      ) : null}
    </div>
  );
}
