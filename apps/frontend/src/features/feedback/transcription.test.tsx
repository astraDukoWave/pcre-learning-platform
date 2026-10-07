import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { forgetRecording, keepRecording } from "../activities/recorded-speaking/recordings";
import type { AttemptDetail } from "../lesson/types";
import { Transcription } from "./Transcription";
import type { StoredTranscription } from "./transcription";

const ATTEMPT = "00000000-0000-4000-8000-0000000000bb";
const ACTIVITY = "00000000-0000-4000-8000-0000000000cc";
const RUN = "00000000-0000-4000-8000-0000000000aa";

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const ON = { ai_feedback: true, stt: true, voice: false };

function transcribed(extra: Partial<StoredTranscription>): StoredTranscription {
  return {
    run_id: RUN,
    status: "transcribed",
    reason: null,
    kind: "repeat",
    text: "I would like table for two please",
    words: [],
    repeat: null,
    hint_es: null,
    confirmed: null,
    disputed: null,
    ...extra,
  };
}

function renderPanel(
  handler: (req: Request) => Response | Promise<Response>,
  stored: StoredTranscription | null = null,
  onSaved: (detail: AttemptDetail) => void = () => undefined,
) {
  const fetchFn = vi.fn(async (input: Request) => handler(input));
  vi.stubGlobal("fetch", fetchFn);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <Transcription attemptId={ATTEMPT} activityId={ACTIVITY} stored={stored} aiFeedback={null} onSaved={onSaved} />
    </QueryClientProvider>,
  );
  return fetchFn;
}

beforeEach(() => keepRecording(ACTIVITY, { blob: new Blob(["audio"], { type: "audio/webm" }), durationMs: 4200 }));
afterEach(() => {
  forgetRecording(ACTIVITY);
  vi.unstubAllGlobals();
});

describe("transcription", () => {
  it("sends the in-memory recording only when asked and shows recognized words", async () => {
    const sent: { body?: FormData; key?: string | null } = {};
    const fetchFn = renderPanel(async (req) => {
      if (req.url.endsWith("/capabilities")) return json(200, ON);
      sent.key = req.headers.get("Idempotency-Key");
      sent.body = await req.formData();
      return json(200, {
        ...transcribed({
          repeat: { recognized: 7, total: 8, recognized_ratio: 0.875, missing: ["a"] },
          hint_es: "Si dijiste estas palabras y no aparecen, puede ser el reconocimiento.",
        }),
        attempt_id: ATTEMPT,
      });
    });
    await screen.findByRole("button", { name: "Transcribir mi grabación" });
    expect(fetchFn).toHaveBeenCalledTimes(1); // solo las capacidades: el audio no salió
    await userEvent.click(screen.getByRole("button", { name: "Transcribir mi grabación" }));
    expect(await screen.findByText("Palabras reconocidas: 7 de 8")).toBeInTheDocument();
    expect(screen.getByText("a")).toBeInTheDocument();
    expect(screen.getByText(/puede ser el reconocimiento/)).toBeInTheDocument();
    expect(sent.key).toBeTruthy();
    expect(sent.body?.get("attempt_id")).toBe(ATTEMPT);
    expect(sent.body?.get("activity_id")).toBe(ACTIVITY);
    expect(sent.body?.get("duration_ms")).toBe("4200");
    const audio = sent.body?.get("audio") as File;
    expect([audio.type, audio.size]).toEqual(["audio/webm", 5]);
  });

  it("offers nothing to send when transcription is off", async () => {
    const fetchFn = renderPanel(() => json(200, { ...ON, stt: false }));
    expect(await screen.findByText(/no está disponible ahora/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Transcribir mi grabación" })).toBeNull();
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });

  it("asks to confirm an interview before feedback and allows a dispute", async () => {
    const decisions: unknown[] = [];
    const saved: AttemptDetail[] = [];
    renderPanel(
      async (req) => {
        if (req.url.endsWith("/capabilities")) return json(200, ON);
        decisions.push(await req.json());
        return json(200, { id: ATTEMPT, result: {}, evaluation_status: "pending" });
      },
      transcribed({ kind: "interview", text: "On weekends I cook.", confirmed: false, disputed: false }),
      (d) => saved.push(d),
    );
    expect(screen.getByText("Esto entendimos:")).toBeInTheDocument();
    expect(screen.getByText("On weekends I cook.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Pedir feedback (IA)" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Eso no fue lo que dije" }));
    await vi.waitFor(() => expect(saved).toHaveLength(1));
    expect(decisions).toEqual([{ confirmed: false }]);
  });

  it("shows feedback only for a confirmed interview and says when it is being verified", () => {
    renderPanel(
      () => json(200, ON),
      transcribed({ kind: "interview", text: "On weekends I cook.", confirmed: true, disputed: false }),
    );
    expect(screen.getByRole("button", { name: "Pedir feedback (IA)" })).toBeInTheDocument();
  });

  it("does not resend an unknown transcription", async () => {
    renderPanel(() => json(200, ON), { ...transcribed({}), status: "unknown", kind: null, text: null });
    expect(await screen.findByText(/Estamos verificando la transcripción anterior/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Transcribir|Intentar/ })).toBeNull();
  });
});
