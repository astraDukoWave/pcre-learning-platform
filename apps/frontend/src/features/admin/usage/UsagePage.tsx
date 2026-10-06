import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, unwrap } from "../../../api/client";
import { ErrorNotice } from "../../../components/ErrorNotice";
import { Notice } from "../../../components/Notice";
import { Page } from "../../../components/Page";
import styles from "../admin.module.css";
import { reasonLabel, shiftPeriod, usd } from "./money";

const CAPABILITIES: Record<string, string> = {
  ai_feedback: "Feedback con IA",
  stt: "Transcripción",
  voice: "Coach de voz",
};
const PURPOSES: Record<string, string> = {
  writing_feedback: "Feedback de escritura",
  speaking_feedback: "Feedback de habla",
  transcription: "Transcripciones",
  voice_session: "Sesiones de voz",
};

/** Consumo y costo por periodo (MVP-02 REQ-01): presupuesto global, aviso al 80 % y alumnos. */
export function UsagePage() {
  const [period, setPeriod] = useState<string | undefined>(undefined);
  const usage = useQuery({
    queryKey: ["admin-usage", period],
    queryFn: () => unwrap(api.GET("/api/v1/admin/usage", { params: { query: period ? { period } : {} } })),
  });
  const u = usage.data;
  const current = period ?? u?.period;
  return (
    <Page title="Consumo de IA y voz" wide>
      {current ? (
        <div className={styles.tabs} role="group" aria-label="Periodo">
          <button type="button" onClick={() => setPeriod(shiftPeriod(current, -1))}>
            Mes anterior
          </button>
          <span aria-live="polite">{current}</span>
          <button type="button" onClick={() => setPeriod(shiftPeriod(current, 1))}>
            Mes siguiente
          </button>
        </div>
      ) : null}
      <ErrorNotice error={usage.error} />
      {u ? (
        <>
          <p>{u.period_note} Montos estimados con los precios configurados; el gasto real lo confirma cada proveedor.</p>
          {u.global_budget.warning ? (
            <Notice tone="note" title="Presupuesto al 80 % o más">
              Lo gastado más lo reservado ya llega a {usd(u.global_budget.estimated_microusd)} de{" "}
              {usd(u.global_budget.limit_microusd)}.
            </Notice>
          ) : null}
          <h2>Capacidades</h2>
          <ul>
            {u.capabilities.map((c) => (
              <li key={c.capability}>
                {CAPABILITIES[c.capability] ?? c.capability}: {reasonLabel(c.reason)}
              </li>
            ))}
          </ul>
          <h2>Presupuesto global</h2>
          {u.global_budget.configured ? (
            <div className={styles.grid}>
              {[
                ["Tope", usd(u.global_budget.limit_microusd)],
                ["Gastado", usd(u.global_budget.spent_microusd)],
                ["Reservado", usd(u.global_budget.reserved_microusd)],
                ["Estimado", usd(u.global_budget.estimated_microusd)],
              ].map(([label, value]) => (
                <div key={label} className={styles.stat}>
                  <strong>{value}</strong>
                  {label}
                </div>
              ))}
            </div>
          ) : (
            <p>Sin presupuesto configurado: las capacidades con costo están apagadas (fail-closed).</p>
          )}
          <p>
            Tope por alumno: {u.user_limit_microusd === null ? "sin configurar" : usd(u.user_limit_microusd)} · Minutos
            de voz por alumno al mes: {u.voice_minutes_per_user ?? "sin configurar"}.
          </p>
          <h2>Llamadas por tipo</h2>
          {Object.keys(u.calls_by_purpose).length ? (
            <ul>
              {Object.entries(u.calls_by_purpose).map(([purpose, n]) => (
                <li key={purpose}>
                  {PURPOSES[purpose] ?? purpose}: {n}
                </li>
              ))}
            </ul>
          ) : (
            <p>Sin llamadas en el periodo.</p>
          )}
          <h2>Por alumno</h2>
          {u.users.length ? (
            <table className={styles.table}>
              <thead>
                <tr>
                  <th scope="col">Cuenta</th>
                  <th scope="col">Llamadas</th>
                  <th scope="col">Minutos de voz</th>
                  <th scope="col">Reservado</th>
                  <th scope="col">Gastado</th>
                  <th scope="col">Estimado</th>
                  <th scope="col">Por verificar</th>
                </tr>
              </thead>
              <tbody>
                {u.users.map((row) => (
                  <tr key={row.user_id}>
                    <td>{row.email}</td>
                    <td>{row.calls}</td>
                    <td>{(row.voice_seconds / 60).toFixed(1)}</td>
                    <td>{usd(row.reserved_microusd)}</td>
                    <td>{usd(row.spent_microusd)}</td>
                    <td>{usd(row.estimated_microusd)}</td>
                    <td>{row.unknown_runs}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p>Nadie ha usado capacidades con costo en este periodo.</p>
          )}
        </>
      ) : null}
    </Page>
  );
}
