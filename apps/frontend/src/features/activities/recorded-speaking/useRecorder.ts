import { useCallback, useEffect, useRef, useState } from "react";

export type RecorderState =
  | "idle"
  | "preparing"
  | "requesting"
  | "recording"
  | "recorded"
  | "denied"
  | "unsupported"
  | "failed";

/** Grabación local con MediaRecorder: el audio queda en memoria del navegador como
 * `blob:` y no se sube salvo que la alumna pida la transcripción (MVP-02 REQ-04). Se
 * detiene sola al llegar a `maxSeconds`. `onRecorded` recibe el audio y su duración. */
export function useRecorder(
  maxSeconds: number,
  prepSeconds: number,
  onRecorded?: (blob: Blob, durationMs: number) => void,
) {
  const [state, setState] = useState<RecorderState>(() =>
    typeof window !== "undefined" &&
    "MediaRecorder" in window &&
    typeof navigator.mediaDevices?.getUserMedia === "function"
      ? "idle"
      : "unsupported",
  );
  const [url, setUrl] = useState<string | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const timer = useRef<number | null>(null);
  const startedAt = useRef(0);
  const recordedCallback = useRef(onRecorded);
  useEffect(() => {
    recordedCallback.current = onRecorded;
  }, [onRecorded]);

  const clearTimer = useCallback(() => {
    if (timer.current !== null) window.clearInterval(timer.current);
    timer.current = null;
  }, []);
  const releaseStream = useCallback(() => {
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
  }, []);

  const countdown = useCallback(
    (seconds: number, onDone: () => void) => {
      clearTimer();
      setSecondsLeft(seconds);
      let left = seconds;
      timer.current = window.setInterval(() => {
        left -= 1;
        setSecondsLeft(left);
        if (left <= 0) {
          clearTimer();
          onDone();
        }
      }, 1000);
    },
    [clearTimer],
  );

  const stop = useCallback(() => {
    clearTimer();
    if (recorder.current && recorder.current.state !== "inactive") recorder.current.stop();
  }, [clearTimer]);

  const record = useCallback(async () => {
    clearTimer();
    setState("requesting");
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });
    } catch (err) {
      const name = err instanceof DOMException ? err.name : "";
      setState(name === "NotAllowedError" || name === "SecurityError" ? "denied" : "failed");
      return;
    }
    try {
      const chunks: Blob[] = [];
      const rec = new MediaRecorder(stream.current);
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data);
      };
      rec.onstop = () => {
        releaseStream();
        const blob = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
        recordedCallback.current?.(blob, Math.max(1, Math.round(performance.now() - startedAt.current)));
        setUrl((old) => {
          if (old) URL.revokeObjectURL(old);
          return URL.createObjectURL(blob);
        });
        setState("recorded");
      };
      recorder.current = rec;
      startedAt.current = performance.now();
      rec.start();
      setState("recording");
      countdown(maxSeconds, () => {
        if (rec.state !== "inactive") rec.stop();
      });
    } catch {
      releaseStream();
      setState("failed");
    }
  }, [maxSeconds, clearTimer, countdown, releaseStream]);

  const start = useCallback(() => {
    if (prepSeconds > 0) {
      setState("preparing");
      countdown(prepSeconds, () => void record());
    } else {
      void record();
    }
  }, [prepSeconds, record, countdown]);

  useEffect(
    () => () => {
      clearTimer();
      if (recorder.current && recorder.current.state !== "inactive") {
        recorder.current.onstop = null;
        recorder.current.stop();
      }
      releaseStream();
    },
    [clearTimer, releaseStream],
  );
  useEffect(
    () => () => {
      if (url) URL.revokeObjectURL(url);
    },
    [url],
  );

  return { state, url, secondsLeft, start, record, stop };
}
