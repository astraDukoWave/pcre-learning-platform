import { useMutation } from "@tanstack/react-query";
import { useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { api, unwrap } from "../api/client";
import { Button } from "../components/Button";
import { ErrorNotice } from "../components/ErrorNotice";
import { Field } from "../components/Field";
import { Notice } from "../components/Notice";
import { Page } from "../components/Page";
import { useMe, useSetMe } from "../features/auth/session";
import { GoalForm, type GoalValues } from "../features/profile/GoalForm";
import styles from "./Profile.module.css";

export function Profile() {
  const me = useMe();
  const setMe = useSetMe();
  const navigate = useNavigate();
  const dialog = useRef<HTMLDialogElement>(null);
  const [password, setPassword] = useState("");
  const save = useMutation({
    mutationFn: (values: GoalValues) => unwrap(api.PATCH("/api/v1/me", { body: values })),
    onSuccess: (data) => setMe(data),
  });
  const remove = useMutation({
    mutationFn: () => unwrap(api.DELETE("/api/v1/me", { body: { password } })),
    onSuccess: () => {
      setMe(null);
      navigate("/?cuenta=borrada", { replace: true });
    },
  });
  if (!me.data) return null;

  function confirmDelete(e: FormEvent) {
    e.preventDefault();
    remove.mutate();
  }

  return (
    <Page title="Perfil">
      <p>
        Correo: <strong>{me.data.email}</strong>
      </p>
      <h2>Tu meta</h2>
      {save.isSuccess ? <Notice tone="success">Guardado.</Notice> : null}
      <ErrorNotice error={save.error} />
      <GoalForm me={me.data} submitLabel="Guardar cambios" busy={save.isPending} onSubmit={(v) => save.mutate(v)} />

      <h2 className={styles.section}>Tus datos</h2>
      <p>Descarga en un archivo todo lo que guardamos sobre ti: perfil, respuestas, resultados, repasos y comentarios.</p>
      <p>
        <a className={styles.download} href="/api/v1/me/export" download>
          Descargar mis datos
        </a>
      </p>
      <p>Borrar tu cuenta elimina tus datos y cierra tu sesión. No se puede deshacer.</p>
      <Button variant="secondary" onClick={() => dialog.current?.showModal()}>
        Borrar mi cuenta
      </Button>
      <dialog ref={dialog} className={styles.dialog} aria-labelledby="delete-title">
        <form onSubmit={confirmDelete}>
          <h2 id="delete-title">¿Borrar tu cuenta?</h2>
          <p>Escribe tu contraseña para confirmar.</p>
          <ErrorNotice error={remove.error} />
          <Field label="Contraseña" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <div className={styles.actions}>
            <Button variant="quiet" onClick={() => dialog.current?.close()}>
              Cancelar
            </Button>
            <Button type="submit" busy={remove.isPending}>
              Borrar definitivamente
            </Button>
          </div>
        </form>
      </dialog>
    </Page>
  );
}
