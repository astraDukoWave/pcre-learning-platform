import type { components } from "../../api/schema";

export type Lesson = components["schemas"]["LessonOut"];
export type Activity = components["schemas"]["StudentActivityOut"];
export type AttemptSummary = components["schemas"]["AttemptSummaryOut"];
export type AttemptResult = components["schemas"]["AttemptOut"];
export type Passage = components["schemas"]["PassageOut"];

export interface ChoiceOption {
  id: string;
  text: string;
}

export interface ChoiceData {
  options: ChoiceOption[];
  multiple?: boolean;
}

/** Lo que se muestra después de enviar: intento recién creado o el último guardado. */
export interface ShownResult {
  correct: boolean | null;
  evaluation_status: string;
  result: Record<string, unknown>;
  aided: boolean;
  explanation?: string | null;
  response: Record<string, unknown>;
  feedback?: AttemptResult["feedback"];
}
