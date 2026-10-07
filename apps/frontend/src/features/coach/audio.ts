/** Audio del coach de voz (MVP-02 REQ-06), en funciones puras para probarlas sin navegador.
 *
 * - Captura: el worklet entrega Float32 a la frecuencia del `AudioContext` (44.1 o 48 kHz, o la
 *   que imponga Safari iOS); aquí se remuestrea a 16 kHz mono, se pasa a PCM16 y se arma en
 *   frames de 20–40 ms para el servidor.
 * - Reproducción: el servidor manda PCM16 a 24 kHz; se convierte a Float32 para un
 *   `AudioBuffer` de esa frecuencia (el navegador remuestrea al reproducir).
 */

export const CAPTURE_RATE = 16_000;
export const PLAYBACK_RATE = 24_000;
export const FRAME_MS = 40;

/** Remuestreo lineal por bloques. Guarda la última muestra y la posición fraccional del
 * bloque anterior, así una secuencia de bloques da lo mismo que el audio completo. */
export class Resampler {
  private last: number | null = null;
  private pos = 0;

  constructor(
    readonly fromRate: number,
    readonly toRate: number = CAPTURE_RATE,
  ) {}

  process(input: Float32Array): Float32Array {
    if (this.fromRate === this.toRate) return input.slice();
    const src = this.last === null ? input : Float32Array.of(this.last, ...input);
    if (src.length === 0) return new Float32Array(0);
    const step = this.fromRate / this.toRate;
    const out: number[] = [];
    let pos = this.pos;
    while (pos < src.length - 1) {
      const i = Math.floor(pos);
      const frac = pos - i;
      out.push(src[i]! * (1 - frac) + src[i + 1]! * frac);
      pos += step;
    }
    // La última muestra pasa a ser el índice 0 del siguiente bloque.
    this.pos = pos - (src.length - 1);
    this.last = src[src.length - 1]!;
    return Float32Array.from(out);
  }
}

/** Float32 [-1, 1] → PCM16 little-endian con recorte. */
export function toPcm16(samples: Float32Array): Int16Array {
  const out = new Int16Array(samples.length);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]!));
    out[i] = s < 0 ? Math.round(s * 0x8000) : Math.round(s * 0x7fff);
  }
  return out;
}

/** PCM16 little-endian → Float32 para reproducir. Un byte suelto al final se ignora. */
export function fromPcm16(buffer: ArrayBuffer): Float32Array {
  const view = new DataView(buffer);
  const n = Math.floor(buffer.byteLength / 2);
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) out[i] = view.getInt16(i * 2, true) / 0x8000;
  return out;
}

/** Junta muestras PCM16 y entrega frames de `frameMs` (40 ms a 16 kHz = 640 muestras). */
export class FrameChunker {
  private pending: number[] = [];
  readonly frameSamples: number;

  constructor(rate: number = CAPTURE_RATE, frameMs: number = FRAME_MS) {
    this.frameSamples = Math.round((rate * frameMs) / 1000);
  }

  push(samples: Int16Array): Int16Array[] {
    for (const s of samples) this.pending.push(s);
    const frames: Int16Array[] = [];
    while (this.pending.length >= this.frameSamples) {
      frames.push(Int16Array.from(this.pending.splice(0, this.frameSamples)));
    }
    return frames;
  }
}
