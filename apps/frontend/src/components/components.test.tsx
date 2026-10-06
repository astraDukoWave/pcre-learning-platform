import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { NotFound } from "../pages/NotFound";
import { Button } from "./Button";
import { Field } from "./Field";
import { Highlight } from "./Highlight";
import { MarginNote } from "./MarginNote";
import { Notice } from "./Notice";

describe("primitives", () => {
  it("Field links label, hint and error to the input", () => {
    render(<Field label="Correo" hint="El de tu invitación" error="Revisa el correo" />);
    const input = screen.getByLabelText("Correo");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input.getAttribute("aria-describedby")).toContain("-hint");
    expect(screen.getByRole("alert")).toHaveTextContent("Revisa el correo");
  });

  it("Button is a real button and shows the busy state", () => {
    render(<Button busy>Enviar respuesta</Button>);
    const button = screen.getByRole("button", { name: "Enviar respuesta" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
  });

  it("Notice uses alert only for system errors and shows the request id", () => {
    render(<Notice tone="system-error" requestId="abc">Falló</Notice>);
    expect(screen.getByRole("alert")).toHaveTextContent("abc");
  });

  it("MarginNote and Highlight render the learner fragment", () => {
    render(
      <MarginNote title="Revisa esto">
        <Highlight>on 6 p.m.</Highlight>
      </MarginNote>,
    );
    expect(screen.getByText("on 6 p.m.").tagName).toBe("MARK");
  });

  it("NotFound offers a way home", () => {
    render(
      <MemoryRouter>
        <NotFound />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("No encontramos esto.");
    expect(screen.getByRole("link", { name: "Ir a Inicio" })).toHaveAttribute("href", "/");
  });
});
