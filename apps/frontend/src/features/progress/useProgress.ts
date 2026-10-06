import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "../../api/client";
import type { components } from "../../api/schema";

export type Progress = components["schemas"]["LearnerProgressOut"];
export type Ratio = components["schemas"]["RatioOut"];

export const PROGRESS_KEY = ["progress"] as const;

export function useProgress() {
  return useQuery({ queryKey: PROGRESS_KEY, queryFn: () => unwrap(api.GET("/api/v1/me/progress")) });
}

/** Numerador y denominador visibles; con denominador cero, "aún sin medición" (nunca 0 %). */
export function ratioText(r: Ratio, unit = ""): string {
  if (r.total === 0) return "aún sin medición";
  return `${r.correct} de ${r.total}${unit}`;
}

export function nextActionLink(action: Progress["next_action"]): { to: string; label: string } | null {
  if ((action.kind === "lesson" || action.kind === "scenario") && action.item_id) {
    const base = action.kind === "scenario" ? "/escenarios" : "/lecciones";
    const verb = action.reason === "in_progress" ? "Continuar" : "Empezar";
    return { to: `${base}/${action.item_id}`, label: `${verb}: ${action.title ?? ""}` };
  }
  if (action.kind === "review") return { to: "/repasos", label: "Continuar con tus repasos" };
  return null;
}
