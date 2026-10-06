import { useMutation } from "@tanstack/react-query";
import { Link, NavLink, Outlet, useNavigate } from "react-router";
import { api, unwrap } from "../api/client";
import { Notice } from "../components/Notice";
import { UnauthorizedBridge } from "../features/auth/guards";
import { useMe, useSetMe } from "../features/auth/session";
import { es } from "../i18n/es";
import styles from "./Layout.module.css";
import { useOnline } from "./useOnline";

function Nav() {
  const me = useMe();
  const setMe = useSetMe();
  const navigate = useNavigate();
  const logout = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/auth/logout")),
    onSettled: () => {
      setMe(null);
      navigate("/entrar", { replace: true });
    },
  });
  if (!me.data) return null;
  return (
    <nav aria-label="Principal" className={styles.nav}>
      <NavLink to="/inicio">Inicio</NavLink>
      <NavLink to="/ruta">Ruta</NavLink>
      <NavLink to="/perfil">Perfil</NavLink>
      {me.data.role === "admin" ? <NavLink to="/admin/usuarios">Usuarios</NavLink> : null}
      <button type="button" className={styles.logout} onClick={() => logout.mutate()}>
        Salir
      </button>
    </nav>
  );
}

export function Layout() {
  const online = useOnline();
  return (
    <div className={styles.shell}>
      <UnauthorizedBridge />
      <a className={styles.skip} href="#main">
        {es.app.skipToContent}
      </a>
      <header className={styles.header}>
        <Link to="/" className={styles.brand}>
          PCRE
        </Link>
        <span className={styles.tagline}>{es.app.tagline}</span>
        <Nav />
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
        <p>
          <Link to="/privacidad">Aviso de privacidad</Link>
        </p>
      </footer>
    </div>
  );
}
