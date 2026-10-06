import type { ReactNode } from "react";
import styles from "./ActionBar.module.css";

/** Barra inferior fija en teléfono con una sola acción principal por estado. */
export function ActionBar({ children, label = "Acciones" }: { children: ReactNode; label?: string }) {
  return (
    <div className={styles.bar} role="region" aria-label={label}>
      <div className={styles.inner}>{children}</div>
    </div>
  );
}
