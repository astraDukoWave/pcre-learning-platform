import { useMutation } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useLocation } from "react-router";
import { api, unwrap } from "../../api/client";
import { Button } from "../../components/Button";
import { ErrorNotice } from "../../components/ErrorNotice";
import styles from "./feedback.module.css";

/** "Enviar comentario" (REQ-15), siempre disponible en el menú; guarda la página actual
 * como contexto. Usa `<dialog>` nativo: foco atrapado y Escape para cerrar. */
export function FeedbackButton({ className }: { className?: string }) {
  const ref = useRef<HTMLDialogElement>(null);
  const location = useLocation();
  const [message, setMessage] = useState("");
  const send = useMutation({
    mutationFn: () =>
      unwrap(api.POST("/api/v1/feedback", { body: { context_type: "general", message, page: location.pathname } })),
    onSuccess: () => setMessage(""),
  });
  return (
    <>
      <button
        type="button"
        className={className}
        onClick={() => {
          send.reset();
          ref.current?.showModal();
        }}
      >
        Enviar comentario
      </button>
      <dialog ref={ref} className={styles.dialog} aria-labelledby="feedback-title">
        <form
          method="dialog"
          className={styles.form}
          onSubmit={(e) => {
            e.preventDefault();
            send.mutate();
          }}
        >
          <h2 id="feedback-title">Enviar comentario</h2>
          {send.isSuccess ? (
            <p role="status">Gracias. Lo leemos todo.</p>
          ) : (
            <>
              <label className={styles.field}>
                ¿Qué te gustaría contarnos? (se guarda junto con la página en la que estás)
                <textarea value={message} onChange={(e) => setMessage(e.target.value)} maxLength={1000} rows={4} />
              </label>
              <ErrorNotice error={send.error} />
            </>
          )}
          <div className={styles.actions}>
            {!send.isSuccess ? (
              <Button type="submit" disabled={!message.trim()} busy={send.isPending}>
                Enviar
              </Button>
            ) : null}
            <Button variant="quiet" onClick={() => ref.current?.close()}>
              Cerrar
            </Button>
          </div>
        </form>
      </dialog>
    </>
  );
}
