import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, unwrap } from "../../../api/client";
import { ErrorNotice } from "../../../components/ErrorNotice";
import { Page } from "../../../components/Page";
import styles from "../admin.module.css";

/** Panel del piloto (REQ-15): 7 o 28 días, sin cuentas internas en las métricas. */
export function PilotPage() {
  const [days, setDays] = useState<7 | 28>(7);
  const summary = useQuery({
    queryKey: ["pilot", days],
    queryFn: () => unwrap(api.GET("/api/v1/admin/pilot/summary", { params: { query: { days } } })),
  });
  const feedback = useQuery({ queryKey: ["admin-feedback"], queryFn: () => unwrap(api.GET("/api/v1/admin/feedback")) });
  const s = summary.data;
  return (
    <Page title="Panel del piloto" wide>
      <div className={styles.tabs} role="group" aria-label="Periodo">
        {([7, 28] as const).map((d) => (
          <button key={d} type="button" aria-selected={days === d} aria-pressed={days === d} onClick={() => setDays(d)}>
            Últimos {d} días
          </button>
        ))}
      </div>
      <ErrorNotice error={summary.error ?? feedback.error} />
      {s ? (
        <>
          <p>Las cuentas internas no cuentan en estas métricas.</p>
          <div className={styles.grid}>
            {[
              ["Intentos", s.attempts],
              ["Lecciones completadas", s.lessons_completed],
              ["Repasos hechos", s.reviews_done],
              ["Repasos vencidos hoy", s.reviews_due],
              ["Diagnósticos", s.diagnostics],
              ["Checkpoints", s.checkpoints],
              ["Valoración media", s.average_rating === null ? "aún sin medición" : `${s.average_rating} (${s.ratings})`],
              ["Reportes abiertos", s.open_reports],
              ["Errores del servidor", s.server_errors],
            ].map(([label, value]) => (
              <div key={String(label)} className={styles.stat}>
                <strong>{value}</strong>
                {label}
              </div>
            ))}
          </div>
          <h2>Alumnos activos por día</h2>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Día</th>
                <th scope="col">Alumnos</th>
              </tr>
            </thead>
            <tbody>
              {s.active_by_day.map((d) => (
                <tr key={d.day}>
                  <td>{d.day}</td>
                  <td>{d.students}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <h2>Últimos comentarios</h2>
          {s.latest_comments.length ? (
            <ul>
              {s.latest_comments.map((c) => (
                <li key={c.id}>
                  {c.email} · {c.context_type}
                  {c.rating ? ` · ${c.rating}/5` : ""}: {c.message}
                </li>
              ))}
            </ul>
          ) : (
            <p>Sin comentarios en el periodo.</p>
          )}
          <h2>Últimos errores del servidor</h2>
          {s.latest_errors.length ? (
            <ul>
              {s.latest_errors.map((e) => (
                <li key={e.request_id + e.occurred_at}>
                  {e.status_code} · {e.route} · {e.error_code} · <code>{e.request_id}</code>
                </li>
              ))}
            </ul>
          ) : (
            <p>Sin errores en el periodo.</p>
          )}
        </>
      ) : summary.isPending ? (
        <p>Cargando…</p>
      ) : null}
      {feedback.data ? (
        <>
          <h2>Valoración por lección</h2>
          {feedback.data.by_lesson.length ? (
            <table className={styles.table}>
              <thead>
                <tr>
                  <th scope="col">Lección</th>
                  <th scope="col">Media</th>
                  <th scope="col">Valoraciones</th>
                </tr>
              </thead>
              <tbody>
                {feedback.data.by_lesson.map((l) => (
                  <tr key={l.item_id}>
                    <td>{l.title}</td>
                    <td>{l.average}</td>
                    <td>{l.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p>Aún sin valoraciones.</p>
          )}
        </>
      ) : null}
    </Page>
  );
}
