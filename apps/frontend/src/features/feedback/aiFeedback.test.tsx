import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AiFeedback } from "./AiFeedback";
import { reasonText, segments } from "./aiFeedback";

const TEXT = "Dear Sir, could you tell me which days do the classes meet? Thanks.";
const RUN = "00000000-0000-4000-8000-0000000000aa";
const ATTEMPT = "00000000-0000-4000-8000-0000000000bb";

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function renderAi(handler: (req: Request) => Response) {
  const fetchFn = vi.fn(async (input: Request) => handler(input));
  vi.stubGlobal("fetch", fetchFn);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <AiFeedback attemptId={ATTEMPT} text={TEXT} stored={null} onSaved={() => undefined} />
    </QueryClientProvider>,
  );
  return fetchFn;
}

afterEach(() => vi.unstubAllGlobals());

describe("AI feedback", () => {
  it("marks literal evidence regardless of case, spacing and quote style", () => {
    const parts = segments("I’d like  to KNOW the price. Thanks", ["i'd like to know", "the price", "missing"]);
    expect(parts.filter((p) => p.note !== null).map((p) => [p.text, p.note])).toEqual([
      ["I’d like  to KNOW", 0],
      ["the price", 1],
    ]);
    expect(parts.map((p) => p.text).join("")).toBe("I’d like  to KNOW the price. Thanks");
    expect(reasonText("other_language")).toBe("tu respuesta no está en inglés");
  });

  it("marks evidence the way the server validates it: edges, dashes and whole words", () => {
    const marked = (text: string, evidence: string) =>
      segments(text, [evidence])
        .filter((p) => p.note !== null)
        .map((p) => p.text);
    const turn = "How much does the course cost?";
    expect(marked(turn, "the course cost?")).toEqual(["the course cost"]);
    expect(marked(turn, '"How much does the course"')).toEqual(["How much does the course"]);
    expect(marked(turn, "How much does the course.")).toEqual(["How much does the course"]);
    expect(marked("Well — I think so.", "Well - I think")).toEqual(["Well — I think"]);
    const parts = segments("a classroom and a class", ["a class"]);
    expect(parts.map((p) => [p.text, p.note])).toEqual([
      ["a classroom and ", null],
      ["a class", 0],
    ]);
    expect(marked(turn, "...")).toEqual([]);
  });

  it("shows notes with highlighted evidence and the AI label", async () => {
    const fetchFn = renderAi((req) => {
      if (req.url.endsWith("/feedback")) {
        expect(req.headers.get("Idempotency-Key")).toBeTruthy();
        return json(200, {
          run_id: RUN,
          attempt_id: ATTEMPT,
          status: "evaluable",
          reason: null,
          label: "Feedback automático orientativo (IA)",
          observations: [
            {
              criterion: "language_control",
              criterion_name_es: "Control del lenguaje",
              evidence: "which days do the classes meet",
              observation_es: "Sin «do» en la pregunta indirecta.",
              suggestion_es: "Escribe «which days the classes meet».",
            },
          ],
          rubric_levels: {},
        });
      }
      return json(200, { id: ATTEMPT, result: {}, evaluation_status: "evaluated" });
    });
    await userEvent.click(screen.getByRole("button", { name: "Pedir feedback (IA)" }));
    expect(await screen.findByText("Feedback automático orientativo (IA)")).toBeInTheDocument();
    expect(screen.getByText("which days do the classes meet", { selector: "mark" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "¿Te sirvió la observación 1?" })).toBeInTheDocument();
    expect(fetchFn).toHaveBeenCalledTimes(2);
  });

  it("offers self-assessment when the capability is off", async () => {
    renderAi(() =>
      json(503, {
        error: { code: "capability_disabled", message: "Esta práctica no está disponible ahora.", request_id: "r" },
      }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Pedir feedback (IA)" }));
    expect(
      await screen.findByText("El feedback no está disponible ahora. Puedes autoevaluarte con la rúbrica."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Pedir feedback (IA)" })).toBeNull();
  });

  it("explains a not evaluable answer and an unknown result without retrying", async () => {
    renderAi(() =>
      json(200, {
        run_id: RUN,
        attempt_id: ATTEMPT,
        status: "unknown",
        reason: "timeout",
        label: "Feedback automático orientativo (IA)",
        observations: [],
        rubric_levels: {},
      }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Pedir feedback (IA)" }));
    expect(await screen.findByText(/Estamos verificando el feedback anterior/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /feedback|Intentar/ })).toBeNull();
  });
});
