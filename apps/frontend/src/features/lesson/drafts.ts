import { newIdempotencyKey } from "../../api/client";

/** Borrador local de una respuesta: comodidad del navegador, nunca la fuente de verdad.
 * Guarda también la clave de idempotencia para reintentar con la misma (EDGE-03). */
export interface Draft {
  response: Record<string, unknown>;
  key: string;
}

const PREFIX = "pcre:draft:";

export function loadDraft(activityId: string): Draft | null {
  try {
    const raw = sessionStorage.getItem(PREFIX + activityId);
    return raw ? (JSON.parse(raw) as Draft) : null;
  } catch {
    return null;
  }
}

export function saveDraft(activityId: string, response: Record<string, unknown>): Draft {
  const existing = loadDraft(activityId);
  const draft = { response, key: existing?.key ?? newIdempotencyKey() };
  try {
    sessionStorage.setItem(PREFIX + activityId, JSON.stringify(draft));
  } catch {
    // Sin almacenamiento (modo privado): la respuesta sigue en memoria.
  }
  return draft;
}

export function clearDraft(activityId: string): void {
  try {
    sessionStorage.removeItem(PREFIX + activityId);
  } catch {
    // nada que limpiar
  }
}

/** Tras un 409 `idempotency_conflict` (el envío anterior se guardó con otra respuesta y su
 * confirmación se perdió), la respuesta nueva necesita otra clave: será otro intento. */
export function renewDraftKey(activityId: string, response: Record<string, unknown>): Draft {
  clearDraft(activityId);
  return saveDraft(activityId, response);
}
