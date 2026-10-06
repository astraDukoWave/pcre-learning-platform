import { useEffect, type ReactNode } from "react";
import styles from "./Page.module.css";

export interface PageProps {
  title: string;
  /** Título visible; por defecto el mismo que el del documento. */
  heading?: ReactNode;
  children: ReactNode;
  wide?: boolean;
}

export function Page({ title, heading, children, wide = false }: PageProps) {
  useEffect(() => {
    document.title = `${title} · PCRE`;
  }, [title]);
  return (
    <section className={[styles.page, wide ? styles.wide : ""].join(" ")} aria-labelledby="page-title">
      <h1 id="page-title" tabIndex={-1}>
        {heading ?? title}
      </h1>
      {children}
    </section>
  );
}
