import { Fragment } from "react";
import type { WordCompletionData } from "../../lesson/types";
import styles from "./WordCompletionRenderer.module.css";

export interface WordCompletionRendererProps {
  data: WordCompletionData;
  answers: Record<string, string>;
  onChange: (answers: Record<string, string>) => void;
  disabled: boolean;
  perGap?: Record<string, boolean> | null;
}

const GAP = /\{\{([a-z0-9]{1,8})\}\}/g;

/** Párrafo con campos en línea: el inicio de cada palabra se ve y el alumno escribe el
 * resto (o la palabra completa). Cada campo dice qué hueco es y con qué empieza. */
export function WordCompletionRenderer({ data, answers, onChange, disabled, perGap }: WordCompletionRendererProps) {
  const shown = Object.fromEntries(data.gaps.map((g) => [g.id, g.shown]));
  const order = data.gaps.map((g) => g.id);
  const parts = data.text_en.split(GAP);
  return (
    <p className={styles.text} lang="en">
      {parts.map((part, i) => {
        if (i % 2 === 0) return <Fragment key={i}>{part}</Fragment>;
        const id = part;
        const n = order.indexOf(id) + 1;
        const state = perGap ? (perGap[id] ? styles.ok : styles.review) : "";
        return (
          <span key={i} className={styles.gap}>
            <span aria-hidden="true">{shown[id]}</span>
            <input
              className={[styles.input, state].join(" ")}
              value={answers[id] ?? ""}
              onChange={(e) => onChange({ ...answers, [id]: e.target.value })}
              disabled={disabled}
              maxLength={60}
              autoComplete="off"
              autoCapitalize="off"
              spellCheck={false}
              aria-label={`Hueco ${n} de ${order.length}: la palabra empieza con «${shown[id]}»`}
              size={Math.max(4, (answers[id] ?? "").length + 1)}
            />
          </span>
        );
      })}
    </p>
  );
}
