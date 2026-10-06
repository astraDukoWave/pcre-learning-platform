import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { api, unwrap } from "../../api/client";
import { Button } from "../../components/Button";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Notice } from "../../components/Notice";
import styles from "./feedback.module.css";

/** Al terminar una lección o un escenario (REQ-15): utilidad de 1 a 5, comentario opcional
 * (≤ 1 000) y la opción de omitir. */
export function LessonRating({ itemId, noun }: { itemId: string; noun: string }) {
  const [rating, setRating] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const [skipped, setSkipped] = useState(false);
  const send = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/feedback", {
          body: { context_type: "lesson", context_id: itemId, rating, message, page: window.location.pathname },
        }),
      ),
  });
  if (skipped) return null;
  if (send.isSuccess) return <Notice tone="success">Gracias: tu valoración ayuda a mejorar las lecciones.</Notice>;
  return (
    <form
      className={styles.form}
      onSubmit={(e) => {
        e.preventDefault();
        send.mutate();
      }}
    >
      <fieldset className={styles.scale}>
        <legend>¿Qué tan útil fue {noun}?</legend>
        {[1, 2, 3, 4, 5].map((n) => (
          <label key={n}>
            <input type="radio" name={`rating-${itemId}`} value={n} checked={rating === n} onChange={() => setRating(n)} />
            {n}
          </label>
        ))}
      </fieldset>
      <p className={styles.hint}>1 = nada útil · 5 = muy útil</p>
      <label className={styles.field}>
        Comentario (opcional)
        <textarea value={message} onChange={(e) => setMessage(e.target.value)} maxLength={1000} rows={3} />
      </label>
      <ErrorNotice error={send.error} />
      <div className={styles.actions}>
        <Button type="submit" disabled={rating === null} busy={send.isPending}>
          Enviar valoración
        </Button>
        <Button variant="quiet" onClick={() => setSkipped(true)}>
          Omitir
        </Button>
      </div>
    </form>
  );
}
