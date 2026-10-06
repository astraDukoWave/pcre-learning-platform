import type { ReactNode } from "react";
import styles from "./Highlight.module.css";

/** Marcatextos sobre el fragmento exacto del alumno. El único movimiento de la interfaz:
 * recorre el fragmento en 250 ms al llegar el feedback; con movimiento reducido, aparece. */
export function Highlight({ children, animate = true }: { children: ReactNode; animate?: boolean }) {
  return <mark className={[styles.mark, animate ? styles.animate : ""].join(" ")}>{children}</mark>;
}
