import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import { api, unwrap } from "../api/client";
import { Button } from "../components/Button";
import { ErrorNotice } from "../components/ErrorNotice";
import { Field } from "../components/Field";
import { Page } from "../components/Page";
import { homeFor, useSetMe } from "../features/auth/session";
import { tokenFromHash } from "./AcceptInvite";

export function ResetPassword() {
  const location = useLocation();
  const navigate = useNavigate();
  const setMe = useSetMe();
  const token = tokenFromHash(location.hash);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const info = useQuery({
    queryKey: ["reset", token],
    queryFn: () => unwrap(api.POST("/api/v1/auth/password-reset/inspect", { body: { token } })),
    enabled: token.length >= 20,
    retry: false,
  });
  const reset = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/auth/password-reset/confirm", {
          body: { token, password, password_confirm: confirm },
        }),
      ),
    onSuccess: (me) => {
      setMe(me);
      navigate(homeFor(me), { replace: true });
    },
  });

  if (token.length < 20 || info.isError) {
    return (
      <Page title="Este enlace ya no sirve">
        <p>Este enlace ya no sirve. Pide uno nuevo al equipo.</p>
        <Link to="/entrar">Ir a Entrar</Link>
      </Page>
    );
  }
  function submit(e: FormEvent) {
    e.preventDefault();
    reset.mutate();
  }
  return (
    <Page title="Elige una contraseña nueva">
      {info.data ? <p>Cuenta: {info.data.email}. Al guardar se cerrarán tus otras sesiones.</p> : null}
      <ErrorNotice error={reset.error} />
      <form onSubmit={submit} noValidate>
        <Field label="Contraseña nueva" type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <Field label="Confírmala" type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        <Button type="submit" busy={reset.isPending}>
          Guardar contraseña
        </Button>
      </form>
    </Page>
  );
}
