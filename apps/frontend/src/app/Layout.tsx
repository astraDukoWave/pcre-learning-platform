import { Link, Outlet } from "react-router";
import { Notice } from "../components/Notice";
import { es } from "../i18n/es";
import styles from "./Layout.module.css";
import { useOnline } from "./useOnline";

export function Layout() {
  const online = useOnline();
  return (
    <div className={styles.shell}>
      <a className={styles.skip} href="#main">
        {es.app.skipToContent}
      </a>
      <header className={styles.header}>
        <Link to="/" className={styles.brand}>
          PCRE
        </Link>
        <span className={styles.tagline}>{es.app.tagline}</span>
      </header>
      {!online ? (
        <div className={styles.offline}>
          <Notice tone="system-error">{es.common.offline}</Notice>
        </div>
      ) : null}
      <main id="main" tabIndex={-1} className={styles.main}>
        <Outlet />
      </main>
      <footer className={styles.footer}>
        <p>{es.app.trademark}</p>
      </footer>
    </div>
  );
}
