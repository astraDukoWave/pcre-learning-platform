import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import type { GuidedDialogueData } from "../lesson/types";
import { GuidedDialogueRenderer, walk } from "./guided-dialogue/GuidedDialogueRenderer";
import { RecordedSpeakingRenderer } from "./recorded-speaking/RecordedSpeakingRenderer";
import { SentenceOrderRenderer } from "./sentence-order/SentenceOrderRenderer";
import { countWords, ShortWritingRenderer } from "./short-writing/ShortWritingRenderer";
import { WordCompletionRenderer } from "./word-completion/WordCompletionRenderer";

const DIALOGUE: GuidedDialogueData = {
  start: "n1",
  nodes: [
    {
      id: "n1",
      speaker: "agent",
      text_en: "Hi! How can I help?",
      options: [
        { id: "a", text: "What time are the classes?", next: "n2" },
        { id: "b", text: "Bye.", next: null },
      ],
    },
    { id: "n2", speaker: "agent", text_en: "From 6 to 8 p.m.", options: [] },
  ],
};

function Ordered({ tokens }: { tokens: string[] }) {
  const [order, setOrder] = useState<string[]>([]);
  return (
    <>
      <SentenceOrderRenderer data={{ tokens }} order={order} onChange={setOrder} disabled={false} />
      <output data-testid="order">{order.join(" ")}</output>
    </>
  );
}

describe("activity renderers", () => {
  it("word completion shows the visible start and labels each gap", () => {
    let answers: Record<string, string> = {};
    render(
      <WordCompletionRenderer
        data={{
          text_en: "We {{g1}} by bus and {{g2}} home.",
          gaps: [
            { id: "g1", shown: "trav" },
            { id: "g2", shown: "wa" },
          ],
        }}
        answers={{}}
        onChange={(next) => (answers = next)}
        disabled={false}
      />,
    );
    const first = screen.getByLabelText("Hueco 1 de 2: la palabra empieza con «trav»");
    fireEvent.change(first, { target: { value: "el" } });
    expect(answers).toEqual({ g1: "el" });
    expect(screen.getByLabelText("Hueco 2 de 2: la palabra empieza con «wa»")).toBeInTheDocument();
  });

  it("sentence order builds by tapping and moves a selected token with the keyboard", () => {
    render(<Ordered tokens={["walk", "I", "the", "dog", "the"]} />);
    for (const word of ["I", "walk", "the", "the", "dog"]) {
      const [token] = screen.getAllByRole("button", { name: word });
      if (!token) throw new Error(`falta la ficha ${word}`);
      fireEvent.click(token);
    }
    expect(screen.getByTestId("order")).toHaveTextContent("I walk the the dog");
    const dog = screen.getByRole("button", { name: "dog, posición 5" });
    fireEvent.click(dog);
    expect(dog).toHaveAttribute("aria-pressed", "true");
    fireEvent.keyDown(dog, { key: "ArrowLeft" });
    expect(screen.getByTestId("order")).toHaveTextContent("I walk the dog the");
    fireEvent.click(screen.getByRole("button", { name: "Quitar" }));
    expect(screen.getByTestId("order")).toHaveTextContent("I walk the the");
  });

  it("short writing counts words against the range", () => {
    expect(countWords("  Dear   Ana,\nhello  ")).toBe(3);
    render(
      <ShortWritingRenderer
        data={{ min_words: 3, max_words: 5 }}
        text="One two"
        onChange={() => undefined}
        disabled={false}
        label="Correo"
      />,
    );
    expect(screen.getByText("2 palabras · objetivo: entre 3 y 5")).toBeInTheDocument();
  });

  it("guided dialogue walks the graph and ends on a node without options", () => {
    expect(walk(DIALOGUE, []).current?.id).toBe("n1");
    const done = walk(DIALOGUE, ["n1.a"]);
    expect(done.finished).toBe(true);
    expect(done.turns.map((t) => t.node.id)).toEqual(["n1", "n2"]);
    expect(walk(DIALOGUE, ["n1.b"]).finished).toBe(true);
    let path: string[] = [];
    render(<GuidedDialogueRenderer data={DIALOGUE} path={[]} onChange={(p) => (path = p)} disabled={false} />);
    fireEvent.click(screen.getByRole("button", { name: "What time are the classes?" }));
    expect(path).toEqual(["n1.a"]);
  });

  it("guided dialogue shows per-option feedback only when the server sends it", () => {
    render(
      <GuidedDialogueRenderer
        data={DIALOGUE}
        path={["n1.a"]}
        onChange={() => undefined}
        disabled
        turnFeedback={{
          "n1.a": { feedback_es: "Pregunta directa.", good: true },
        }}
      />,
    );
    expect(screen.getByText(/Pregunta directa\./)).toBeInTheDocument();
  });

  it("recorded speaking says the audio stays on the device and offers a path without a microphone", () => {
    let response: Record<string, unknown> = {};
    render(
      <RecordedSpeakingRenderer
        activityId="act-1"
        data={{
          subtype: "interview",
          question_en: "What do you do on weekends?",
          response_seconds: 45,
        }}
        response={{}}
        onChange={(r) => (response = r)}
        disabled={false}
        plays={0}
        onPlay={() => undefined}
      />,
    );
    expect(screen.getByText(/Tu grabación se queda en tu dispositivo\./)).toBeInTheDocument();
    // jsdom no tiene MediaRecorder: es el camino "este navegador no permite grabar".
    expect(screen.getByText("No pude grabar")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Continuar sin grabar" }));
    expect(response).toEqual({ recorded: false });
  });
});
