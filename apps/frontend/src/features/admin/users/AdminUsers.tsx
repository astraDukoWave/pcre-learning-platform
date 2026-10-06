import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, unwrap } from "../../../api/client";
import { Button } from "../../../components/Button";
import { ErrorNotice } from "../../../components/ErrorNotice";
import { Field } from "../../../components/Field";
import { Notice } from "../../../components/Notice";
import { Page } from "../../../components/Page";
import styles from "./AdminUsers.module.css";

const USERS = ["admin", "users"] as const;

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleString("es-MX", { dateStyle: "medium", timeStyle: "short" });
}

function OneTimeLink({ label, url, expiresAt }: { label: string; url: string; expiresAt: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Notice tone="info" title={label}>
      <p>Se muestra una sola vez. Cópialo y mándalo por un canal privado.</p>
      <p className={styles.link}>
        <code>{url}</code>
      </p>
      <p>Vence: {formatDate(expiresAt)}</p>
      <Button
        variant="secondary"
        onClick={() => {
          void navigator.clipboard.writeText(url).then(() => setCopied(true));
        }}
      >
        {copied ? "Copiado" : "Copiar enlace"}
      </Button>
    </Notice>
  );
}

export function AdminUsers() {
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [link, setLink] = useState<{ label: string; url: string; expires_at: string } | null>(null);
  const users = useQuery({ queryKey: USERS, queryFn: () => unwrap(api.GET("/api/v1/admin/users")) });
  const refresh = () => qc.invalidateQueries({ queryKey: USERS });

  const invite = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/admin/invitations", { body: { email } })),
    onSuccess: (data) => {
      setLink({ label: `Invitación para ${email}`, ...data });
      setEmail("");
    },
  });
  const reset = useMutation({
    mutationFn: (u: { id: string; email: string }) =>
      unwrap(api.POST("/api/v1/admin/users/{user_id}/reset-link", { params: { path: { user_id: u.id } } })).then(
        (data) => ({ ...data, email: u.email }),
      ),
    onSuccess: (data) => setLink({ label: `Enlace de reset para ${data.email}`, url: data.url, expires_at: data.expires_at }),
  });
  const revoke = useMutation({
    mutationFn: (id: string) =>
      unwrap(api.POST("/api/v1/admin/users/{user_id}/revoke-sessions", { params: { path: { user_id: id } } })),
    onSuccess: refresh,
  });
  const [notice, setNotice] = useState<string | null>(null);
  const diagnostic = useMutation({
    mutationFn: (u: { id: string; email: string }) =>
      unwrap(
        api.POST("/api/v1/admin/users/{user_id}/diagnostic-reset", { params: { path: { user_id: u.id } } }),
      ).then(() => u.email),
    onSuccess: (who) => setNotice(`Diagnóstico reiniciado para ${who}: puede hacerlo de nuevo.`),
  });
  const internal = useMutation({
    mutationFn: (u: { id: string; is_internal: boolean }) =>
      unwrap(
        api.PATCH("/api/v1/admin/users/{user_id}", {
          params: { path: { user_id: u.id } },
          body: { is_internal: u.is_internal },
        }),
      ),
    onSuccess: refresh,
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    setLink(null);
    invite.mutate();
  }

  return (
    <Page title="Usuarios" wide>
      <h2>Invitar a una alumna o alumno</h2>
      <form onSubmit={submit} className={styles.invite} noValidate>
        <Field label="Correo" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <Button type="submit" busy={invite.isPending}>
          Crear invitación
        </Button>
      </form>
      <ErrorNotice error={invite.error ?? reset.error ?? revoke.error ?? internal.error ?? diagnostic.error} />
      {notice ? <Notice tone="success">{notice}</Notice> : null}
      {link ? <OneTimeLink label={link.label} url={link.url} expiresAt={link.expires_at} /> : null}

      <h2>Cuentas</h2>
      {users.isPending ? <p>Cargando…</p> : null}
      <ErrorNotice error={users.error} />
      {users.data && users.data.length === 0 ? <p>Aún no hay cuentas. Crea la primera invitación.</p> : null}
      <ul className={styles.list}>
        {users.data?.map((u) => (
          <li key={u.id} className={styles.row}>
            <div>
              <strong>{u.email}</strong> {u.role === "admin" ? <span>(admin)</span> : null}
              {u.is_internal ? <span className={styles.tag}> · interna</span> : null}
              <div className={styles.meta}>
                Alta: {formatDate(u.created_at)} · Último acceso: {formatDate(u.last_login_at)} · Sesiones activas:{" "}
                {u.active_sessions}
              </div>
            </div>
            <div className={styles.actions}>
              <Button variant="quiet" onClick={() => reset.mutate({ id: u.id, email: u.email })}>
                Enlace de reset
              </Button>
              <Button variant="quiet" onClick={() => revoke.mutate(u.id)}>
                Cerrar sesiones
              </Button>
              {u.role === "student" ? (
                <Button variant="quiet" onClick={() => diagnostic.mutate({ id: u.id, email: u.email })}>
                  Reiniciar diagnóstico
                </Button>
              ) : null}
              <label className={styles.toggle}>
                <input
                  type="checkbox"
                  checked={u.is_internal}
                  onChange={(e) => internal.mutate({ id: u.id, is_internal: e.target.checked })}
                />{" "}
                Cuenta interna
              </label>
            </div>
          </li>
        ))}
      </ul>
    </Page>
  );
}
