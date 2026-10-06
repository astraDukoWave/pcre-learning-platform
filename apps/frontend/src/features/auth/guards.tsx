import { useQueryClient } from "@tanstack/react-query";
import { useEffect, type ReactNode } from "react";
import { Navigate, useLocation, useNavigate } from "react-router";
import { setUnauthorizedHandler } from "../../api/client";
import { Notice } from "../../components/Notice";
import { Page } from "../../components/Page";
import { es } from "../../i18n/es";
import { ME_KEY, useMe } from "./session";

/** Ante un 401 en cualquier llamada: limpia la sesión y lleva a "Entrar" con `next`. */
export function UnauthorizedBridge() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const location = useLocation();
  useEffect(() => {
    setUnauthorizedHandler(() => {
      qc.setQueryData(ME_KEY, null);
      const next = encodeURIComponent(location.pathname + location.search);
      navigate(`/entrar?next=${next}&motivo=sesion`, { replace: true });
    });
    return () => setUnauthorizedHandler(() => undefined);
  }, [navigate, qc, location.pathname, location.search]);
  return null;
}

export function RequireAuth({ children, admin = false }: { children: ReactNode; admin?: boolean }) {
  const me = useMe();
  const location = useLocation();
  if (me.isPending) return <p className="visually-hidden">{es.common.loading}</p>;
  if (me.isError) {
    return (
      <Page title={es.errors.unexpected}>
        <Notice tone="system-error">{es.errors.network}</Notice>
      </Page>
    );
  }
  if (!me.data) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/entrar?next=${next}`} replace />;
  }
  if (admin && me.data.role !== "admin") {
    return (
      <Page title={es.errors.forbidden}>
        <Notice tone="info">{es.errors.forbidden}</Notice>
      </Page>
    );
  }
  return <>{children}</>;
}
