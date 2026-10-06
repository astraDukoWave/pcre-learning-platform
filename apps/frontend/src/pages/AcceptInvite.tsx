import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import { api, unwrap } from "../api/client";
import { Button } from "../components/Button";
import { ErrorNotice } from "../components/ErrorNotice";
import { Field } from "../components/Field";
import { Page } from "../components/Page";
import { useSetMe } from "../features/auth/session";
import styles from "./AcceptInvite.module.css";

/** El token viaja en el fragmento (`#t=`), que el navegador nunca envía al servidor. */
export function tokenFromHash(hash: string): string {
  return new URLSearchParams(hash.replace(/^#/, "")).get("t") ?? "";
}

export function AcceptInvite() {
  const location = useLocation();
  const navigate = useNavigate();
  const setMe = useSetMe();
  const token = tokenFromHash(location.hash);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [privacy, setPrivacy] = useState(false);
  const [adult, setAdult] = useState(false);
  const [name, setName] = useState("");

  const info = useQuery({
    queryKey: ["invitation", token],
    queryFn: () => unwrap(api.POST("/api/v1/auth/invitations/inspect", { body: { token } })),
    enabled: token.length >= 20,
    retry: false,
  });

  const accept = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/auth/invitations/accept", {
          body: {
            token,
            password,
            password_confirm: confirm,
            accept_privacy: privacy,
            consent_version: info.data?.consent_version ?? "",
            adult,
            display_name: name || null,
          },
        }),
      ),
    onSuccess: (me) => {
      setMe(me);
      navigate("/bienvenida", { replace: true });
    },
  });

  if (token.length < 20 || info.isError) {
    return (
      <Page title="Este enlace ya no sirve">
        <p>Este enlace ya no sirve. Pide uno nuevo a quien te invitó.</p>
        <Link to="/entrar">Ir a Entrar</Link>
      </Page>
    );
  }
  if (!info.data) return <Page title="Crea tu acceso">Cargando…</Page>;

  function submit(e: FormEvent) {
    e.preventDefault();
    accept.mutate();
  }

  return (
    <Page title="Crea tu acceso">
      <p>
        Te invitaron con el correo <strong>{info.data.email}</strong>.
      </p>
      <ErrorNotice error={accept.error} />
      <form onSubmit={submit} noValidate>
        <Field label="Correo" value={info.data.email} readOnly disabled />
        <Field
          label="Contraseña"
          hint="Entre 10 y 128 caracteres. Una frase larga es más fácil de recordar."
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <Field
          label="Confirma tu contraseña"
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
        <Field label="Cómo quieres que te llamemos (opcional)" value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
        <div className={styles.checks}>
          <label>
            <input type="checkbox" checked={privacy} onChange={(e) => setPrivacy(e.target.checked)} /> Leí y acepto el{" "}
            <Link to="/privacidad" target="_blank" rel="noopener">
              aviso de privacidad
            </Link>{" "}
            (versión {info.data.consent_version}).
          </label>
          <label>
            <input type="checkbox" checked={adult} onChange={(e) => setAdult(e.target.checked)} /> Confirmo que soy
            mayor de edad.
          </label>
        </div>
        <Button type="submit" busy={accept.isPending}>
          Crear mi acceso
        </Button>
      </form>
    </Page>
  );
}
