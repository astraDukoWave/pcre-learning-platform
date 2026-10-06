import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { safeNext } from "../features/auth/session";
import { AcceptInvite, tokenFromHash } from "./AcceptInvite";
import { Login } from "./Login";

type Handler = (req: Request) => Response | Promise<Response>;

function stubApi(handler: Handler) {
  const fetchFn = vi.fn(async (input: Request) => handler(input));
  vi.stubGlobal("fetch", fetchFn);
  return fetchFn;
}

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function wrap(ui: ReactNode, path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/entrar" element={ui} />
          <Route path="/aceptar" element={ui} />
          <Route path="/bienvenida" element={<p>onboarding</p>} />
          <Route path="/inicio" element={<p>inicio</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const ME = {
  id: "00000000-0000-4000-8000-000000000001",
  email: "ana@example.com",
  role: "student",
  display_name: null,
  timezone: "America/Mexico_City",
  goal_purpose: null,
  target_exam: null,
  target_exam_other: null,
  target_score: null,
  target_date: null,
  self_reported_level: null,
  onboarded: true,
  consent_version: "v1",
  csrf_token: "csrf",
};

afterEach(() => vi.unstubAllGlobals());

describe("auth pages", () => {
  it("reads the token from the URL fragment, never from the query", () => {
    expect(tokenFromHash("#t=abc")).toBe("abc");
    expect(tokenFromHash("")).toBe("");
  });

  it("only allows internal next paths", () => {
    expect(safeNext("/perfil")).toBe("/perfil");
    expect(safeNext("//evil.example.com")).toBeNull();
    expect(safeNext("https://evil.example.com")).toBeNull();
  });

  it("shows the generic login error and then signs in", async () => {
    let attempts = 0;
    stubApi(async (req) => {
      if (req.url.endsWith("/api/v1/me")) return json(401, { error: { code: "unauthorized", message: "x", request_id: "r" } });
      attempts += 1;
      if (attempts === 1) return json(401, { error: { code: "invalid_credentials", message: "Correo o contraseña incorrectos.", request_id: "r" } });
      return json(200, ME);
    });
    wrap(<Login />, "/entrar");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Correo"), "ana@example.com");
    await user.type(screen.getByLabelText("Contraseña"), "una frase segura");
    await user.click(screen.getByRole("button", { name: "Entrar" }));
    expect(await screen.findByText("Correo o contraseña incorrectos.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Entrar" }));
    await waitFor(() => expect(screen.getByText("inicio")).toBeInTheDocument());
  });

  it("shows the invitation email as read-only", async () => {
    stubApi(async (req) => {
      if (req.url.endsWith("/inspect")) return json(200, { email: "nueva@example.com", consent_version: "v1", expires_at: "2026-10-08T00:00:00Z" });
      return json(401, {});
    });
    wrap(<AcceptInvite />, "/aceptar#t=abcdefghijklmnopqrstuvwxyz0123456789");
    expect(await screen.findByDisplayValue("nueva@example.com")).toHaveAttribute("readonly");
    expect(screen.getByText(/versión v1/)).toBeInTheDocument();
  });

  it("explains an expired invitation", async () => {
    stubApi(async () => json(410, { error: { code: "link_invalid", message: "Este enlace ya no sirve.", request_id: "r" } }));
    wrap(<AcceptInvite />, "/aceptar#t=abcdefghijklmnopqrstuvwxyz0123456789");
    expect(await screen.findByText("Este enlace ya no sirve. Pide uno nuevo a quien te invitó.")).toBeInTheDocument();
  });
});
