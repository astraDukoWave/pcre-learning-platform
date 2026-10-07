import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode, useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { type VoiceSession, VoiceFeedback, voiceReason } from "./VoiceFeedback";

const SESSION_ID = "00000000-0000-4000-8000-0000000000cc";
const RUN = "00000000-0000-4000-8000-0000000000aa";

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const FEEDBACK = {
  status: "evaluable",
  reason: null,
  run_id: RUN,
  label: "Feedback automático orientativo (IA)",
  observations: [
    {
      criterion: "required_moves",
      criterion_name_es: "Movimientos",
      evidence: "How much does the course",
      observation_es: "Preguntaste el precio.",
      suggestion_es: "Agrega «per month».",
      turn: 4,
    },
  ],
  rubric_levels: {},
  hidden: 0,
};

function session(overrides: Partial<VoiceSession> = {}): VoiceSession {
  return {
    id: SESSION_ID,
    scenario_id: "00000000-0000-4000-8000-0000000000dd",
    status: "ended",
    ws_path: `/ws/voice/${SESSION_ID}`,
    max_seconds: 300,
    save_transcript: true,
    created_at: "2026-10-07T12:00:00Z",
    deadline_at: "2026-10-07T12:05:30Z",
    started_at: "2026-10-07T12:00:05Z",
    ended_at: "2026-10-07T12:02:00Z",
    end_reason: "user_stop",
    duration_s: 115,
    learner_speech_s: 42,
    aids: [],
    transcript: [
      { n: 1, role: "coach", text: "Hi! How can I help you?", at_s: 0, aid: false, disputed: false },
      { n: 2, role: "learner", text: "I want to join a course.", at_s: 3, aid: false, disputed: false },
      { n: 3, role: "learner", text: "Could you repeat that, please?", at_s: 6, aid: true, disputed: false },
      { n: 4, role: "learner", text: "How much does the course cost?", at_s: 9, aid: false, disputed: false },
    ],
    feedback: null,
    ...overrides,
  } as VoiceSession;
}

function Harness({ initial }: { initial: VoiceSession }) {
  const [current, setCurrent] = useState(initial);
  return <VoiceFeedback session={current} onSession={setCurrent} />;
}

function renderWith(initial: VoiceSession, handler: (req: Request) => Response | Promise<Response>) {
  const fetchFn = vi.fn(async (input: Request) => handler(input));
  vi.stubGlobal("fetch", fetchFn);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  // StrictMode como en main.tsx: monta dos veces y la petición automática sigue siendo una.
  render(
    <StrictMode>
      <QueryClientProvider client={qc}>
        <Harness initial={initial} />
      </QueryClientProvider>
    </StrictMode>,
  );
  return fetchFn;
}

const posts = (fetchFn: ReturnType<typeof vi.fn>) =>
  (fetchFn.mock.calls as [Request][]).filter(([r]) => r.method === "POST").map(([r]) => r);

afterEach(() => vi.unstubAllGlobals());

describe("voice session feedback", () => {
  it("asks once with a key, shows the note and highlights the evidence in its turn", async () => {
    const fetchFn = renderWith(session(), (req) => {
      if (req.method === "POST" && req.url.endsWith("/feedback")) {
        expect(req.headers.get("Idempotency-Key")).toBeTruthy();
        return json(200, FEEDBACK);
      }
      return json(200, session({ feedback: FEEDBACK as VoiceSession["feedback"] }));
    });
    expect(await screen.findByText("Preguntaste el precio.")).toBeInTheDocument();
    expect(screen.getByText("Feedback automático orientativo (IA)")).toBeInTheDocument();
    // La evidencia se marca solo en el turno citado (el 4), con el número de su observación.
    const items = [...document.querySelectorAll("details li")];
    const cited = items.find((li) => li.textContent?.includes("cost?"));
    expect(cited?.querySelector("mark")?.textContent).toBe("How much does the course1");
    const other = items.find((li) => li.textContent?.includes("I want to join a course."));
    expect(other?.querySelector("mark")).toBeNull();
    // El turno de ayuda no se puede disputar; los propios sí.
    expect(screen.getAllByRole("button", { name: /Eso no fue lo que dije/ })).toHaveLength(2);
    expect(fetchFn.mock.calls.filter(([r]) => r.method === "POST")).toHaveLength(1);
  });

  it("a disputed turn hides its note", async () => {
    let disputed = false;
    renderWith(session({ feedback: FEEDBACK as VoiceSession["feedback"] }), (req) => {
      expect(req.url).toContain("/turns/4/flag");
      disputed = true;
      const base = session();
      return json(
        200,
        session({
          transcript: base.transcript?.map((t) => (t.n === 4 ? { ...t, disputed: true } : t)),
          feedback: { ...FEEDBACK, observations: [], hidden: 1 } as VoiceSession["feedback"],
        }),
      );
    });
    expect(screen.getByText("Preguntaste el precio.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Eso no fue lo que dije (turno 4)" }));
    await waitFor(() => expect(screen.queryByText("Preguntaste el precio.")).not.toBeInTheDocument());
    expect(disputed).toBe(true);
    expect(screen.getByText(/Ocultamos 1 observación/)).toBeInTheDocument();
    const item = screen.getByText("How much does the course cost?").closest("li");
    expect(within(item as HTMLElement).getByText(/Marcaste que no fue lo que dijiste/)).toBeInTheDocument();
  });

  it("explains too little speech and asks nothing without consent", async () => {
    expect(voiceReason("too_little_speech")).toContain("menos de 30 segundos");
    const fetchFn = renderWith(session({ save_transcript: false, transcript: null }), () =>
      json(500, {}),
    );
    expect(screen.getByText(/no marcaste la casilla/)).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it("each observation can be rated with its index in the evaluator output", async () => {
    const shown = { ...FEEDBACK, observations: [{ ...FEEDBACK.observations[0], index: 1 }] };
    const fetchFn = renderWith(session({ feedback: shown as VoiceSession["feedback"] }), () =>
      json(201, { id: "00000000-0000-4000-8000-0000000000ee" }),
    );
    await userEvent.click(screen.getByRole("button", { name: /Me sirvió/ }));
    await waitFor(() => expect(fetchFn).toHaveBeenCalledTimes(1));
    const body = (await (fetchFn.mock.calls[0]?.[0] as Request).json()) as Record<string, unknown>;
    expect(body).toMatchObject({ context_type: "ai_observation", context_id: RUN, observation: 1, rating: 1 });
  });

  it("offers a retry after a failed feedback", async () => {
    let calls = 0;
    renderWith(session(), (req) => {
      if (req.method === "POST") {
        calls += 1;
        return json(200, { status: "failed", reason: "http_503", run_id: RUN, observations: [], hidden: 0 });
      }
      return json(200, session());
    });
    const retry = await screen.findByRole("button", { name: "Pedir el feedback otra vez" });
    await userEvent.click(retry);
    await waitFor(() => expect(calls).toBe(2));
  });

  it("after a failed result the retry uses a new key; after a network error, the same key", async () => {
    let n = 0;
    const fetchFn = renderWith(session(), (req) => {
      if (req.method !== "POST") return json(200, session());
      n += 1;
      if (n === 1) return json(200, { status: "failed", reason: "http_503", run_id: RUN, observations: [], hidden: 0 });
      if (n === 2) throw new TypeError("Failed to fetch");
      return json(200, FEEDBACK);
    });
    await userEvent.click(await screen.findByRole("button", { name: "Pedir el feedback otra vez" }));
    await userEvent.click(await screen.findByRole("button", { name: "Pedir el feedback otra vez" }));
    expect(await screen.findByText("Preguntaste el precio.")).toBeInTheDocument();
    const keys = posts(fetchFn).map((r) => r.headers.get("Idempotency-Key"));
    expect(keys).toHaveLength(3);
    expect(keys[1]).not.toBe(keys[0]); // tras `failed`, otra clave
    expect(keys[2]).toBe(keys[1]); // tras una falla de red, la misma
  });

  it("waits for the session to close, then shows the result", async () => {
    let n = 0;
    renderWith(session(), (req) => {
      if (req.method !== "POST") return json(200, session({ feedback: FEEDBACK as VoiceSession["feedback"] }));
      n += 1;
      return n === 1
        ? json(409, { error: { code: "voice_session_open", message: "La sesión sigue abierta." } })
        : json(200, FEEDBACK);
    });
    expect(await screen.findByText("Preguntaste el precio.", {}, { timeout: 3000 })).toBeInTheDocument();
  });

  it("unknown, unavailable and not evaluable explain themselves without a dead end", async () => {
    renderWith(session(), () =>
      json(200, { status: "unknown", reason: "timeout", run_id: RUN, observations: [], hidden: 0 }),
    );
    expect(await screen.findByText(/Estamos verificando/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Pedir el feedback otra vez" })).toBeNull();
    cleanup();
    renderWith(session(), () =>
      json(503, { error: { code: "capability_disabled", message: "No disponible." } }),
    );
    expect(await screen.findByText("El feedback no está disponible ahora.")).toBeInTheDocument();
    expect(screen.getAllByText("El feedback no está disponible ahora.")).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "Pedir el feedback otra vez" })).toBeNull();
    cleanup();
    renderWith(session({ learner_speech_s: 12 }), (req) =>
      req.method === "POST"
        ? json(200, { status: "not_evaluable", reason: "too_little_speech", observations: [], hidden: 0 })
        : json(200, session()),
    );
    // Visible y anunciado en la región viva.
    expect(await screen.findAllByText(/hablaste menos de 30 segundos/)).toHaveLength(2);
    expect(screen.getByRole("status")).toHaveTextContent(/hablaste menos de 30 segundos/);
  });

  it("re-reads a session whose transcript was not saved yet", async () => {
    const fetchFn = renderWith(session({ status: "active", transcript: null }), (req) =>
      req.method === "POST"
        ? json(503, { error: { code: "capability_disabled", message: "No disponible." } })
        : json(200, session()),
    );
    expect(await screen.findByText(/Transcripción \(4 turnos\)/)).toBeInTheDocument();
    expect((fetchFn.mock.calls as [Request][]).some(([r]) => r.method === "GET")).toBe(true);
  });

  it("flag buttons wait while the feedback is being analysed", async () => {
    let release: (r: Response) => void = () => undefined;
    renderWith(session(), (req) =>
      req.method === "POST" ? new Promise<Response>((resolve) => (release = resolve)) : json(200, session()),
    );
    const buttons = await screen.findAllByRole("button", { name: /Eso no fue lo que dije/ });
    expect(buttons.every((b) => (b as HTMLButtonElement).disabled)).toBe(true);
    release(json(200, FEEDBACK));
    await waitFor(() =>
      expect(
        screen.getAllByRole("button", { name: /Eso no fue lo que dije/ }).every((b) => !(b as HTMLButtonElement).disabled),
      ).toBe(true),
    );
  });
});
