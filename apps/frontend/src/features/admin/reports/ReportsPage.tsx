import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, unwrap } from "../../../api/client";
import type { components } from "../../../api/schema";
import { Button } from "../../../components/Button";
import { ErrorNotice } from "../../../components/ErrorNotice";
import { Page } from "../../../components/Page";
import styles from "../admin.module.css";

type Report = components["schemas"]["ReportOut"];
type Status = Report["status"];

const STATUS: Record<Status, string> = {
  open: "Abierto",
  triaged: "En revisión",
  resolved: "Resuelto",
  wont_fix: "No se corrige",
};
const CATEGORY: Record<string, string> = {
  answer_key: "La respuesta correcta está mal",
  unclear: "No se entiende",
  audio: "Audio",
  typo: "Errata",
  other: "Otro",
};

function Triage({ report }: { report: Report }) {
  const qc = useQueryClient();
  const [status, setStatus] = useState<Status>(report.status);
  const [note, setNote] = useState(report.triage_note ?? "");
  const save = useMutation({
    mutationFn: () =>
      unwrap(
        api.PATCH("/api/v1/admin/content-reports/{report_id}", {
          params: { path: { report_id: report.id } },
          body: { status, triage_note: note || null },
        }),
      ),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["admin-reports"] }),
  });
  return (
    <form
      className={styles.form}
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <label>
        Estado
        <select value={status} onChange={(e) => setStatus(e.target.value as Status)}>
          {Object.entries(STATUS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </label>
      <label>
        Nota de triage
        <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={1000} />
      </label>
      <ErrorNotice error={save.error} />
      <Button type="submit" variant="secondary" busy={save.isPending}>
        Guardar
      </Button>
    </form>
  );
}

/** Reportes de contenido del alumno con triage (REQ-15). */
export function ReportsPage() {
  const [filter, setFilter] = useState<Status | "">("open");
  const reports = useQuery({
    queryKey: ["admin-reports", filter],
    queryFn: () =>
      unwrap(api.GET("/api/v1/admin/content-reports", { params: { query: { status: filter || undefined } } })),
  });
  return (
    <Page title="Reportes de contenido" wide>
      <div className={styles.filters}>
        <label>
          Estado
          <select value={filter} onChange={(e) => setFilter(e.target.value as Status | "")}>
            <option value="">Todos</option>
            {Object.entries(STATUS).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
      </div>
      <ErrorNotice error={reports.error} />
      {reports.data && reports.data.length === 0 ? <p>No hay reportes con este estado.</p> : null}
      {reports.data?.map((r) => (
        <article key={r.id} className={styles.card} aria-label={`Reporte ${r.item_title ?? ""}`}>
          <p>
            <strong>{r.item_title}</strong> · {CATEGORY[r.category] ?? r.category} · {STATUS[r.status]} ·{" "}
            {new Date(r.created_at).toLocaleString("es-MX")}
          </p>
          {r.message ? <p>{r.message}</p> : null}
          {r.page ? <p className={styles.tag}>{r.page}</p> : null}
          <Triage report={r} />
        </article>
      ))}
    </Page>
  );
}
