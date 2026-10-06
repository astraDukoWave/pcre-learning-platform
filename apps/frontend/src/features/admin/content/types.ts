import type { components } from "../../../api/schema";

export type RevisionRow = components["schemas"]["RevisionRowOut"];
export type RevisionDetail = components["schemas"]["RevisionDetailOut"];
export type AdminUnit = components["schemas"]["AdminUnitOut"];

export const STATUS_LABEL: Record<string, string> = {
  draft: "Borrador",
  approved: "Aprobada",
  published: "Publicada",
  superseded: "Reemplazada",
  withdrawn: "Retirada",
};

export const KIND_LABEL: Record<string, string> = {
  lesson: "Lección",
  scenario: "Escenario",
  assessment_form: "Comprobación",
};
