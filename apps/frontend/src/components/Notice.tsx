import type { ReactNode } from "react";
import styles from "./Notice.module.css";

type Tone = "info" | "success" | "system-error" | "note";

export interface NoticeProps {
  tone?: Tone;
  title?: ReactNode;
  children?: ReactNode;
  requestId?: string | null;
}

/** Avisos del sistema. Los errores de aprendizaje usan `note` (morado), nunca rojo. */
export function Notice({ tone = "info", title, children, requestId }: NoticeProps) {
  const role = tone === "system-error" ? "alert" : "status";
  return (
    <div className={[styles.notice, styles[tone]].join(" ")} role={role}>
      {title ? <p className={styles.title}>{title}</p> : null}
      {children ? <div>{children}</div> : null}
      {requestId ? (
        <p className={styles.meta}>
          Código de la petición: <code>{requestId}</code>
        </p>
      ) : null}
    </div>
  );
}
