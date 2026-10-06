import type { components } from "../../api/schema";

type MePatch = components["schemas"]["MePatch"];
export type GoalPurpose = NonNullable<MePatch["goal_purpose"]>;
export type TargetExam = NonNullable<MePatch["target_exam"]>;
export type SelfLevel = NonNullable<MePatch["self_reported_level"]>;

export const PURPOSES: { value: GoalPurpose; label: string }[] = [
  { value: "work", label: "Trabajo" },
  { value: "studies", label: "Estudios" },
  { value: "certification", label: "Certificación" },
  { value: "other", label: "Otro" },
  { value: "unknown", label: "No lo sé" },
];

export const EXAMS: { value: TargetExam; label: string }[] = [
  { value: "toefl_ibt", label: "TOEFL iBT" },
  { value: "ielts_academic", label: "IELTS Academic" },
  { value: "cambridge_b2_first", label: "Cambridge B2 First" },
  { value: "toefl_itp", label: "TOEFL ITP" },
  { value: "other", label: "Otro" },
  { value: "unknown", label: "No lo sé" },
];

export const LEVELS: { value: SelfLevel; label: string }[] = [
  { value: "A2", label: "A2" },
  { value: "B1", label: "B1" },
  { value: "B2", label: "B2" },
  { value: "unknown", label: "No lo sé" },
];

export function detectedTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "America/Mexico_City";
  } catch {
    return "America/Mexico_City";
  }
}

export function timezones(current: string): string[] {
  let all: string[];
  try {
    all = Intl.supportedValuesOf("timeZone");
  } catch {
    all = [];
  }
  return Array.from(new Set([current, "America/Mexico_City", ...all])).sort();
}
