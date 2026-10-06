import type { components } from "../../api/schema";

export type Lesson = components["schemas"]["LessonOut"];
export type Activity = components["schemas"]["StudentActivityOut"];
export type AttemptSummary = components["schemas"]["AttemptSummaryOut"];
export type AttemptDetail = components["schemas"]["AttemptDetailOut"];
export type AttemptResult = components["schemas"]["AttemptOut"];
export type AttemptFeedback = components["schemas"]["AttemptFeedbackOut"];
export type Passage = components["schemas"]["PassageOut"];

export interface ChoiceOption {
  id: string;
  text: string;
}

export interface ChoiceData {
  options: ChoiceOption[];
  multiple?: boolean;
}

export interface WordCompletionData {
  text_en: string;
  gaps: { id: string; shown: string }[];
}

export interface SentenceOrderData {
  tokens: string[];
}

export interface ShortWritingData {
  min_words: number;
  max_words: number;
}

export interface RecordedSpeakingData {
  subtype: "listen_and_repeat" | "interview";
  audio_url?: string | null;
  question_en?: string | null;
  prep_seconds?: number;
  response_seconds: number;
}

export interface DialogueOption {
  id: string;
  text: string;
  next?: string | null;
}

export interface DialogueNode {
  id: string;
  speaker: "agent" | "narrator";
  text_en: string;
  options: DialogueOption[];
}

export interface GuidedDialogueData {
  start: string;
  nodes: DialogueNode[];
}

export interface RubricCriterion {
  id: string;
  name_es: string;
  levels: { score: number; descriptor_es: string }[];
  self_assessed_only?: boolean;
}

export interface Rubric {
  id: string;
  version: number;
  name_es: string;
  criteria: RubricCriterion[];
  note_es?: string | null;
}

/** Lo que se muestra después de enviar: intento recién creado o el último guardado. */
export interface ShownResult {
  id?: string;
  correct: boolean | null;
  evaluation_status: string;
  result: Record<string, unknown>;
  aided: boolean;
  explanation?: string | null;
  response: Record<string, unknown>;
  feedback?: AttemptFeedback;
}
