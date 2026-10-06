import type { components } from "../../api/schema";

export type AssessmentForm = components["schemas"]["AssessmentFormOut"];
export type AssessmentRun = components["schemas"]["AssessmentRunOut"];
export type ItemResult = components["schemas"]["ItemResultOut"];
export type RunSummary = components["schemas"]["RunSummaryOut"];

const SKILLS: Record<string, string> = {
  R: "Lectura",
  L: "Escucha",
  W: "Escritura",
  S: "Habla",
  T: "Transferencia",
};

/** "U1.R" → "Unidad 1 · Lectura" (los códigos son estables, contrato §4). */
export function objectiveLabel(code: string): string {
  const match = /^U(\d)\.([RLWST])/.exec(code);
  if (!match) return code;
  return `Unidad ${match[1]} · ${SKILLS[match[2] ?? ""] ?? match[2]}`;
}
