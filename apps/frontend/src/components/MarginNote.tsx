import type { ReactNode } from "react";
import styles from "./MarginNote.module.css";

export interface MarginNoteProps {
  tone?: "note" | "ok";
  title?: ReactNode;
  children: ReactNode;
}

/** Nota al margen: el feedback junto a la respuesta. "Revisa esto" en morado, nunca rojo. */
export function MarginNote({ tone = "note", title, children }: MarginNoteProps) {
  return (
    <aside className={[styles.note, styles[tone]].join(" ")} aria-live="polite">
      {title ? (
        <p className={styles.title}>
          <span aria-hidden="true" className={styles.icon}>
            {tone === "ok" ? "✓" : "✎"}
          </span>{" "}
          {title}
        </p>
      ) : null}
      <div className={styles.body}>{children}</div>
    </aside>
  );
}
