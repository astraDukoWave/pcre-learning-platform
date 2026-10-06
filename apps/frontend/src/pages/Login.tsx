import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router";
import { api, unwrap } from "../api/client";
import { Button } from "../components/Button";
import { ErrorNotice } from "../components/ErrorNotice";
import { Field } from "../components/Field";
import { Notice } from "../components/Notice";
import { Page } from "../components/Page";
import { es } from "../i18n/es";
import { homeFor, safeNext, useMe, useSetMe } from "../features/auth/session";

export function Login() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const me = useMe();
  const setMe = useSetMe();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const next = safeNext(params.get("next"));

  const login = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/auth/login", { body: { email, password } })),
    onSuccess: (data) => {
      setMe(data);
      navigate(data.onboarded && next ? next : homeFor(data), { replace: true });
    },
  });

  if (me.data) return <Navigate to={next ?? homeFor(me.data)} replace />;

  function submit(e: FormEvent) {
    e.preventDefault();
    login.mutate();
  }

  return (
    <Page title="Entrar">
      {params.get("motivo") === "sesion" ? <Notice tone="info">{es.errors.sessionExpired}</Notice> : null}
      <ErrorNotice error={login.error} />
      <form onSubmit={submit} noValidate>
        <Field
          label="Correo"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Field
          label="Contraseña"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <Button type="submit" busy={login.isPending}>
          Entrar
        </Button>
      </form>
      <p>
        ¿Olvidaste tu contraseña? Pide un enlace nuevo a quien te invitó. <Link to="/privacidad">Aviso de privacidad</Link>
      </p>
    </Page>
  );
}
