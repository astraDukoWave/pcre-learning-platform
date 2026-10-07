import { useCallback, useMemo, useRef } from "react";
import { FrameChunker, Resampler, toPcm16 } from "./audio";

export type CaptureError = "denied" | "unsupported" | "failed";

/** Micrófono → AudioWorklet → PCM16 a 16 kHz en frames de 40 ms. `start` debe llamarse desde
 * un gesto del usuario (Safari iOS solo deja arrancar el `AudioContext` así). */
export function useVoiceCapture(onFrame: (frame: ArrayBuffer) => void) {
  const ctx = useRef<AudioContext | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const node = useRef<AudioWorkletNode | null>(null);

  const stop = useCallback(() => {
    node.current?.port.close();
    node.current?.disconnect();
    stream.current?.getTracks().forEach((t) => t.stop());
    void ctx.current?.close().catch(() => undefined);
    node.current = null;
    stream.current = null;
    ctx.current = null;
  }, []);

  const start = useCallback(async (): Promise<CaptureError | null> => {
    if (typeof AudioContext === "undefined" || !navigator.mediaDevices?.getUserMedia) return "unsupported";
    const audio = new AudioContext();
    ctx.current = audio;
    try {
      await audio.resume();
      stream.current = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
    } catch (err) {
      stop();
      const name = err instanceof DOMException ? err.name : "";
      return name === "NotAllowedError" || name === "SecurityError" ? "denied" : "failed";
    }
    try {
      await audio.audioWorklet.addModule(new URL("./pcm-worklet.js", import.meta.url));
      const source = audio.createMediaStreamSource(stream.current);
      const worklet = new AudioWorkletNode(audio, "pcm-capture");
      // La frecuencia real del contexto (Safari iOS puede imponer la suya).
      const resampler = new Resampler(audio.sampleRate);
      const chunker = new FrameChunker();
      worklet.port.onmessage = (e: MessageEvent<Float32Array>) => {
        for (const frame of chunker.push(toPcm16(resampler.process(e.data)))) {
          onFrame(frame.buffer as ArrayBuffer);
        }
      };
      source.connect(worklet);
      node.current = worklet;
      return null;
    } catch {
      stop();
      return "failed";
    }
  }, [onFrame, stop]);

  return useMemo(() => ({ start, stop }), [start, stop]);
}
