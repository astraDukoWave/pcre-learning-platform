import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { usePcmPlayback } from "./usePcmPlayback";

/** `AudioContext` mínimo: jsdom no trae Web Audio. */
class FakeAudioContext {
  static created: FakeAudioContext[] = [];
  currentTime = 0;
  destination = {};
  closed = false;
  rates: number[] = [];

  constructor() {
    FakeAudioContext.created.push(this);
  }

  resume() {
    return Promise.resolve();
  }

  close() {
    this.closed = true;
    return Promise.resolve();
  }

  createBuffer(_channels: number, length: number, rate: number) {
    this.rates.push(rate);
    return { duration: length / rate, copyToChannel: () => undefined };
  }

  createBufferSource() {
    return { buffer: null, connect: () => undefined, start: () => undefined, stop: () => undefined, onended: null };
  }
}

function context(i: number): FakeAudioContext {
  const ctx = FakeAudioContext.created[i];
  if (!ctx) throw new Error(`no hay AudioContext ${i}`);
  return ctx;
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  FakeAudioContext.created = [];
});

describe("coach playback", () => {
  it("lets the queued phrase finish for at most two seconds, then closes", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("AudioContext", FakeAudioContext);
    const { result } = renderHook(() => usePcmPlayback());
    await act(() => result.current.prime());
    result.current.enqueue(new ArrayBuffer(24_000 * 2 * 3)); // 3 s de PCM16 a 24 kHz
    const first = context(0);
    result.current.finish(2);
    expect(first.closed).toBe(false);
    vi.advanceTimersByTime(1999);
    expect(first.closed).toBe(false);
    vi.advanceTimersByTime(1);
    expect(first.closed).toBe(true);
  });

  it("a new start gets its own context and plays at the announced rate", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("AudioContext", FakeAudioContext);
    const { result } = renderHook(() => usePcmPlayback());
    await act(() => result.current.prime());
    result.current.finish(2);
    await act(() => result.current.prime());
    expect(FakeAudioContext.created).toHaveLength(2);
    result.current.setRate(16_000);
    result.current.enqueue(new ArrayBuffer(3200));
    expect(context(1).rates).toEqual([16_000]);
    vi.advanceTimersByTime(2000);
    expect(context(1).closed).toBe(false);
  });
});
