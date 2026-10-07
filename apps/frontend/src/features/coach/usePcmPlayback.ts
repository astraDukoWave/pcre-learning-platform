import { useCallback, useMemo, useRef } from "react";
import { PLAYBACK_RATE, fromPcm16 } from "./audio";

/** Cola de reproducción del audio del coach (PCM16; 24 kHz salvo que `ready` diga otra
 * frecuencia). `flush` corta lo que suena y vacía la cola cuando el alumno empieza a hablar
 * (puede interrumpir al coach). */
export function usePcmPlayback(rate: number = PLAYBACK_RATE) {
  const ctx = useRef<AudioContext | null>(null);
  const sampleRate = useRef(rate);
  const nextAt = useRef(0);
  const playing = useRef(new Set<AudioBufferSourceNode>());

  /** Desde el gesto de "Empezar": desbloquea el audio en Safari iOS. */
  const prime = useCallback(async () => {
    if (typeof AudioContext === "undefined") return;
    ctx.current ??= new AudioContext();
    await ctx.current.resume().catch(() => undefined);
  }, []);

  const enqueue = useCallback(
    (chunk: ArrayBuffer) => {
      const audio = ctx.current;
      if (!audio || chunk.byteLength < 2) return;
      const samples = fromPcm16(chunk);
      const buffer = audio.createBuffer(1, samples.length, sampleRate.current);
      buffer.copyToChannel(samples as Float32Array<ArrayBuffer>, 0);
      const source = audio.createBufferSource();
      source.buffer = buffer;
      source.connect(audio.destination);
      const at = Math.max(audio.currentTime, nextAt.current);
      source.start(at);
      nextAt.current = at + buffer.duration;
      playing.current.add(source);
      source.onended = () => playing.current.delete(source);
    },
    [],
  );

  /** La frecuencia que anuncia el servidor en `ready` (`VOICE_OUTPUT_SAMPLE_RATE`). */
  const setRate = useCallback(
    (next: number | null | undefined) => {
      sampleRate.current = next && next > 0 ? next : rate;
    },
    [rate],
  );

  const flush = useCallback(() => {
    for (const source of playing.current) {
      try {
        source.stop();
      } catch {
        // ya terminó
      }
    }
    playing.current.clear();
    nextAt.current = ctx.current?.currentTime ?? 0;
  }, []);

  const close = useCallback(() => {
    flush();
    void ctx.current?.close().catch(() => undefined);
    ctx.current = null;
  }, [flush]);

  /** Al terminar la sesión, el coach acaba su frase: lo que ya está en cola suena hasta
   * `maxSeconds` (EDGE-13: 2 s como máximo) y luego se cierra. Un nuevo `prime` crea otro
   * contexto, así que «Intentar de nuevo» no se cruza con este cierre. */
  const finish = useCallback((maxSeconds: number) => {
    const audio = ctx.current;
    ctx.current = null;
    playing.current = new Set();
    if (!audio) return;
    const left = Math.max(0, Math.min(maxSeconds, nextAt.current - audio.currentTime));
    nextAt.current = 0;
    window.setTimeout(() => void audio.close().catch(() => undefined), left * 1000);
  }, []);

  return useMemo(
    () => ({ prime, enqueue, flush, close, finish, setRate }),
    [prime, enqueue, flush, close, finish, setRate],
  );
}
