import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { api, unwrap } from "../../api/client";
import { Button } from "../../components/Button";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Notice } from "../../components/Notice";
import styles from "./feedback.module.css";

const CATEGORIES = [
  { value: "answer_key", label: "La respuesta correcta está mal" },
  { value: "unclear", label: "La instrucción no se entiende" },
  { value: "audio", label: "El audio falla" },
  { value: "typo", label: "Hay una errata" },
  { value: "other", label: "Otro" },
] as const;
type Category = (typeof CATEGORIES)[number]["value"];

/** "Reportar un problema" en cada actividad (REQ-15): va ligado a la revisión exacta. */
export function ReportProblem({
  revisionId,
  activityId,
  attemptId,
}: {
  revisionId: string;
  activityId: string;
  attemptId?: string;
}) {
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState<Category>("unclear");
  const [message, setMessage] = useState("");
  const send = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/content-reports", {
          body: {
            revision_id: revisionId,
            activity_id: activityId,
            attempt_id: attemptId ?? null,
            category,
            message,
            page: window.location.pathname,
          },
        }),
      ),
  });
  if (send.isSuccess) return <Notice tone="success">Gracias por avisar: el equipo lo revisa.</Notice>;
  if (!open) {
    return (
      <Button variant="quiet" onClick={() => setOpen(true)}>
        Reportar un problema
      </Button>
    );
  }
  return (
    <form
      className={styles.form}
      onSubmit={(e) => {
        e.preventDefault();
        send.mutate();
      }}
    >
      <label className={styles.field}>
        ¿Qué pasa?
        <select value={category} onChange={(e) => setCategory(e.target.value as Category)}>
          {CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
      </label>
      <label className={styles.field}>
        Detalle (opcional)
        <textarea value={message} onChange={(e) => setMessage(e.target.value)} maxLength={1000} rows={2} />
      </label>
      <ErrorNotice error={send.error} />
      <div className={styles.actions}>
        <Button type="submit" variant="secondary" busy={send.isPending}>
          Enviar reporte
        </Button>
        <Button variant="quiet" onClick={() => setOpen(false)}>
          Cancelar
        </Button>
      </div>
    </form>
  );
}
