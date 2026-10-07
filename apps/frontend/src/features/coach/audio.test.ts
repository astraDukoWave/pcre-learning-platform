import { describe, expect, it } from "vitest";
import { CAPTURE_RATE, FrameChunker, Resampler, fromPcm16, toPcm16 } from "./audio";

function sine(rate: number, seconds: number, hz = 440): Float32Array {
  const out = new Float32Array(Math.round(rate * seconds));
  for (let i = 0; i < out.length; i++) out[i] = 0.5 * Math.sin((2 * Math.PI * hz * i) / rate);
  return out;
}

describe("coach audio", () => {
  it("resamples 48 kHz to 16 kHz the same in blocks as in one piece", () => {
    const input = sine(48_000, 1);
    const whole = new Resampler(48_000).process(input);
    const blocks = new Resampler(48_000);
    const parts: number[] = [];
    for (let i = 0; i < input.length; i += 128) parts.push(...blocks.process(input.subarray(i, i + 128)));
    expect(Math.abs(whole.length - CAPTURE_RATE)).toBeLessThanOrEqual(1);
    expect(Math.abs(parts.length - whole.length)).toBeLessThanOrEqual(1);
    const n = Math.min(parts.length, whole.length);
    let maxDiff = 0;
    for (let i = 0; i < n; i++) maxDiff = Math.max(maxDiff, Math.abs(parts[i]! - whole[i]!));
    expect(maxDiff).toBeLessThan(1e-6);
  });

  it("handles 44.1 kHz (and Safari's own rate) and leaves 16 kHz untouched", () => {
    expect(Math.abs(new Resampler(44_100).process(sine(44_100, 1)).length - CAPTURE_RATE)).toBeLessThanOrEqual(1);
    const same = sine(16_000, 0.1);
    expect(new Resampler(16_000).process(same)).toEqual(same);
  });

  it("converts to PCM16 with clipping and back", () => {
    const pcm = toPcm16(Float32Array.from([0, 1, -1, 2, -2, 0.5]));
    expect(Array.from(pcm)).toEqual([0, 32767, -32768, 32767, -32768, 16384]);
    const back = fromPcm16(pcm.buffer.slice(0) as ArrayBuffer);
    expect(back[1]).toBeCloseTo(1, 3);
    expect(back[2]).toBe(-1);
    expect(fromPcm16(new Uint8Array([1, 0, 9]).buffer).length).toBe(1); // byte suelto
  });

  it("emits 40 ms frames of 640 samples", () => {
    const chunker = new FrameChunker();
    expect(chunker.frameSamples).toBe(640);
    expect(chunker.push(new Int16Array(500))).toHaveLength(0);
    const frames = chunker.push(new Int16Array(900));
    expect(frames.map((f) => f.length)).toEqual([640, 640]);
    expect(chunker.push(new Int16Array(519))).toHaveLength(0); // quedan 120 + 519 = 639
    expect(chunker.push(new Int16Array(1))).toHaveLength(1);
  });
});
