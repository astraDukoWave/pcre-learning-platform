import createClient, { type Middleware } from "openapi-fetch";
import { networkError, parseError } from "./errors";
import type { paths } from "./schema";

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/** Operaciones que exigen `Idempotency-Key` (§6.1). Si quien llama no trae una clave
 * propia (p. ej. para reintentar con la misma), el wrapper genera una. */
export const IDEMPOTENT_PATHS: RegExp[] = [
  /^\/api\/v1\/attempts$/,
  /^\/api\/v1\/attempts\/[^/]+\/feedback$/,
  /^\/api\/v1\/assessments\/[^/]+\/start$/,
  /^\/api\/v1\/assessment-runs\/[^/]+\/submit$/,
  /^\/api\/v1\/voice-sessions$/,
];

let csrfToken: string | null = null;
let onUnauthorized: () => void = () => undefined;

/** El token CSRF vive solo en memoria; nunca en localStorage (§7). */
export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

export function getCsrfToken(): string | null {
  return csrfToken;
}

export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler;
}

export function newIdempotencyKey(): string {
  return crypto.randomUUID();
}

export const sessionMiddleware: Middleware = {
  onRequest({ request }) {
    if (UNSAFE_METHODS.has(request.method.toUpperCase())) {
      if (csrfToken) request.headers.set("X-CSRF-Token", csrfToken);
      const path = new URL(request.url).pathname;
      if (IDEMPOTENT_PATHS.some((re) => re.test(path)) && !request.headers.has("Idempotency-Key")) {
        request.headers.set("Idempotency-Key", newIdempotencyKey());
      }
    }
    return request;
  },
  onResponse({ response, request }) {
    const path = new URL(request.url).pathname;
    if (response.status === 401 && !path.startsWith("/api/v1/auth/")) onUnauthorized();
    return response;
  },
};

export function createApiClient(baseUrl: string) {
  const client = createClient<paths>({ baseUrl, credentials: "same-origin" });
  client.use(sessionMiddleware);
  return client;
}

export const api = createApiClient(typeof window === "undefined" ? "http://localhost" : window.location.origin);

type Result<T> = { data?: T; error?: unknown; response: Response };

/** Convierte la respuesta de openapi-fetch en datos o en un `ApiError` con `request_id`. */
export async function unwrap<T>(call: Promise<Result<T>>): Promise<T> {
  let result: Result<T>;
  try {
    result = await call;
  } catch {
    throw networkError();
  }
  if (!result.response.ok || result.error !== undefined) {
    throw parseError(result.response.status, result.error, result.response.headers);
  }
  return result.data as T;
}
