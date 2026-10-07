import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
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

function renderWith(initial: VoiceSession, handler: (req: Request) => Response) {
  const fetchFn = vi.fn(async (input: Request) => handler(input));
  vi.stubGlobal("fetch", fetchFn);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <Harness initial={initial} />
    </QueryClientProvider>,
  );
  return fetchFn;
}

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
    expect(screen.getByText(/\(turno 4\)/)).toBeInTheDocument();
    const marks = document.querySelectorAll("li mark");
    expect([...marks].map((m) => m.textContent)).toContain("How much does the course1");
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

  it("explains too little speech, missing consent and lets a failure be retried", async () => {
    expect(voiceReason("too_little_speech")).toContain("menos de 30 segundos");
    renderWith(session({ save_transcript: false, transcript: null }), () => {
      throw new Error("sin consentimiento no se pide nada");
    });
    expect(screen.getByText(/no marcaste la casilla/)).toBeInTheDocument();
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
});
