import type { components } from "../../api/schema";

export type AiFeedback = components["schemas"]["AiFeedbackOut"];
export type AiObservation = components["schemas"]["AiObservationOut"];

export interface Segment {
  text: string;
  /** Índice de la observación que cita este fragmento, o null si es texto sin marcar. */
  note: number | null;
}

const QUOTES = /[‘’'`]/g;
const DQUOTES = /[“”"]/g;
const DASHES = /[–—]/g;
// Lo mismo que quita el validador del servidor de los extremos de una evidencia.
const EDGES = /^[\s.,;:!?"']+|[\s.,;:!?"']+$/g;

function pattern(evidence: string): RegExp | null {
  const cleaned = evidence
    .normalize("NFKC")
    .replace(QUOTES, "'")
    .replace(DQUOTES, '"')
    .replace(DASHES, "-")
    .replace(EDGES, "");
  if (!/[\p{L}\p{N}]/u.test(cleaned)) return null;
  const words = cleaned
    .split(/\s+/)
    .filter(Boolean)
    .map((w) =>
      w
        .replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
        .replace(/'/g, "['‘’`]")
        .replace(/"/g, '["“”]')
        .replace(/-/g, "[-–—]"),
    );
  // Palabras completas, como el servidor: «a class» no se marca dentro de «a classroom».
  return words.length
    ? new RegExp(`(?<![\\p{L}\\p{N}_])${words.join("\\s+")}(?![\\p{L}\\p{N}_])`, "iu")
    : null;
}

/** Parte el texto del alumno en fragmentos y marca la evidencia literal de cada observación
 * (sin distinguir mayúsculas, espacios, tipo de comillas o guiones ni la puntuación de los
 * extremos, y solo en palabras completas: como el validador del servidor).
 * Si dos evidencias se cruzan, gana la que aparece primero. */
export function segments(text: string, evidences: string[]): Segment[] {
  const found: { start: number; end: number; note: number }[] = [];
  evidences.forEach((evidence, note) => {
    const re = pattern(evidence);
    const m = re ? re.exec(text) : null;
    if (m) found.push({ start: m.index, end: m.index + m[0].length, note });
  });
  found.sort((a, b) => a.start - b.start);
  const out: Segment[] = [];
  let cursor = 0;
  for (const f of found) {
    if (f.start < cursor) continue;
    if (f.start > cursor) out.push({ text: text.slice(cursor, f.start), note: null });
    out.push({ text: text.slice(f.start, f.end), note: f.note });
    cursor = f.end;
  }
  if (cursor < text.length) out.push({ text: text.slice(cursor), note: null });
  return out;
}

const REASONS: Record<string, string> = {
  too_short: "tu respuesta es muy corta para comentarla",
  off_topic: "tu respuesta no parece responder a la consigna",
  other_language: "tu respuesta no está en inglés",
  empty: "tu respuesta está vacía",
  invalid_output: "el evaluador no devolvió un comentario válido",
  no_valid_evidence: "el evaluador no pudo citar frases de tu texto",
};

export function reasonText(reason: string | null | undefined): string {
  return (reason && REASONS[reason]) ?? "no fue posible comentarla esta vez";
}
