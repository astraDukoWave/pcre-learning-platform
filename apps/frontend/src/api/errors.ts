import { es } from "../i18n/es";

export interface ApiErrorInit {
  status: number;
  code: string;
  message: string;
  requestId: string | null;
  fields?: { loc: string[]; type: string }[];
  retryAfter?: number | null;
}

/** Error de la API con el sobre `{"error": {code, message, request_id}}` (§6.1). */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string | null;
  readonly fields: { loc: string[]; type: string }[];
  readonly retryAfter: number | null;

  constructor(init: ApiErrorInit) {
    super(init.message);
    this.name = "ApiError";
    this.status = init.status;
    this.code = init.code;
    this.requestId = init.requestId;
    this.fields = init.fields ?? [];
    this.retryAfter = init.retryAfter ?? null;
  }

  get isNetwork(): boolean {
    return this.status === 0;
  }
}

const FALLBACK: Record<number, string> = {
  401: es.errors.sessionExpired,
  403: es.errors.forbidden,
  404: es.errors.notFound,
  429: es.errors.rateLimited,
  500: es.errors.unexpected,
};

interface Envelope {
  error?: { code?: unknown; message?: unknown; request_id?: unknown; fields?: unknown };
}

export function parseError(status: number, body: unknown, headers?: Headers): ApiError {
  const env = (typeof body === "object" && body !== null ? body : {}) as Envelope;
  const err = env.error ?? {};
  const requestId =
    (typeof err.request_id === "string" ? err.request_id : null) ?? headers?.get("X-Request-ID") ?? null;
  const retry = headers?.get("Retry-After");
  return new ApiError({
    status,
    code: typeof err.code === "string" ? err.code : `http_${status}`,
    message:
      typeof err.message === "string" && err.message
        ? err.message
        : (FALLBACK[status] ?? (status >= 500 ? es.errors.unexpected : es.errors.notFound)),
    requestId,
    fields: Array.isArray(err.fields) ? (err.fields as ApiErrorInit["fields"]) : [],
    retryAfter: retry ? Number(retry) : null,
  });
}

export function networkError(): ApiError {
  return new ApiError({ status: 0, code: "network_error", message: es.errors.network, requestId: null });
}
