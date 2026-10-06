import { describe, expect, it, vi } from "vitest";
import { createApiClient, setCsrfToken, setUnauthorizedHandler, unwrap } from "./client";
import { ApiError } from "./errors";

function mockFetch(status: number, body: unknown, headers: Record<string, string> = {}) {
  const fn = vi.fn(async (input: Request) => {
    void input;
    return new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json", ...headers },
    });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

function client() {
  return createApiClient("http://localhost");
}

describe("api client", () => {
  it("adds the CSRF token only to unsafe methods", async () => {
    setCsrfToken("csrf-123");
    const fetchFn = mockFetch(200, { status: "ok" });
    const c = client();
    await c.GET("/health");
    expect(fetchFn.mock.calls[0]![0].headers.get("X-CSRF-Token")).toBeNull();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    await (c as any).POST("/api/v1/attempts", { body: {} });
    const sent: Request = fetchFn.mock.calls[1]![0];
    expect(sent.headers.get("X-CSRF-Token")).toBe("csrf-123");
    setCsrfToken(null);
  });

  it("generates an Idempotency-Key for operations that require it", async () => {
    const fetchFn = mockFetch(200, {});
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const c = client() as any;
    await c.POST("/api/v1/attempts", { body: {} });
    await c.POST("/api/v1/attempts", { body: {}, headers: { "Idempotency-Key": "fixed-key" } });
    await c.POST("/api/v1/auth/logout", { body: {} });
    const [first, second, third] = fetchFn.mock.calls.map((call) => call[0] as Request);
    expect(first!.headers.get("Idempotency-Key")).toMatch(/^[0-9a-f-]{36}$/);
    expect(second!.headers.get("Idempotency-Key")).toBe("fixed-key");
    expect(third!.headers.get("Idempotency-Key")).toBeNull();
  });

  it("turns the error envelope into an ApiError with request_id", async () => {
    mockFetch(404, { error: { code: "not_found", message: "No encontramos esto.", request_id: "req-1" } });
    await expect(unwrap(client().GET("/health"))).rejects.toMatchObject({
      status: 404,
      code: "not_found",
      requestId: "req-1",
    });
  });

  it("reports network failures without pretending success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );
    const error = await unwrap(client().GET("/health")).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).isNetwork).toBe(true);
  });

  it("calls the unauthorized handler on 401 outside /auth", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    mockFetch(401, { error: { code: "unauthorized", message: "x", request_id: "r" } });
    await unwrap(client().GET("/health")).catch(() => undefined);
    expect(handler).toHaveBeenCalledTimes(1);
    setUnauthorizedHandler(() => undefined);
  });
});
