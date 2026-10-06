import { Link } from "react-router";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Page } from "../../components/Page";
import { objectiveLabel } from "../assessment/types";
import styles from "./ProgressPage.module.css";
import { ratioText, useProgress } from "./useProgress";

const AID_LABELS: Record<string, string> = {
  hint: "Pistas",
  support_es: "Apoyos en español",
  transcript: "Transcripciones",
  example: "Ejemplos",
};

/** Métricas de REQ-13 con numerador y denominador; "aún sin medición" sin denominador.
 * Nunca "% de inglés". */
export function ProgressPage() {
  const query = useProgress();
  if (query.isPending) return <Page title="Tu progreso">Cargando…</Page>;
  if (query.isError) {
    return (
      <Page title="Tu progreso">
        <ErrorNotice error={query.error} />
      </Page>
    );
  }
  const p = query.data;
  return (
    <Page title="Tu progreso">
      <p className={styles.period}>Acierto, ayudas y objetivos: últimos {p.period_days} días.</p>
      <dl className={styles.metrics}>
        <div>
          <dt>Avance</dt>
          <dd>
            {ratioText(p.advance, " lecciones")}
            <ul>
              {p.advance.units.map((u) => (
                <li key={u.unit}>
                  {ratioText(u, " lecciones")} de {u.title}
                </li>
              ))}
            </ul>
          </dd>
        </div>
        <div>
          <dt>Acierto inicial</dt>
          <dd>{ratioText(p.initial_accuracy, " primeros intentos correctos")}</dd>
        </div>
        <div>
          <dt>Revisión diferida (sin ayudas)</dt>
          <dd>{ratioText(p.delayed_recall, " repasos correctos")}</dd>
        </div>
        <div>
          <dt>Ayudas usadas</dt>
          <dd>
            {Object.entries(p.aids)
              .map(([k, n]) => `${AID_LABELS[k] ?? k}: ${n}`)
              .join(" · ")}
          </dd>
        </div>
        <div>
          <dt>Producción (autoevaluación)</dt>
          <dd>
            Escritura:{" "}
            {p.production.writing.average === null
              ? "aún sin medición"
              : `${p.production.writing.average} de 3 en ${p.production.writing.count} textos`}
            {" · "}Habla:{" "}
            {p.production.speaking.average === null
              ? "aún sin medición"
              : `${p.production.speaking.average} de 3 en ${p.production.speaking.count} respuestas`}
          </dd>
        </div>
        <div>
          <dt>Racha</dt>
          <dd>{p.streak_days === 1 ? "1 día" : `${p.streak_days} días`} seguidos con al menos un envío</dd>
        </div>
      </dl>
      <section aria-labelledby="reinforce">
        <h2 id="reinforce">Objetivos a reforzar</h2>
        {p.to_reinforce.length === 0 ? (
          <p>Ninguno por ahora.</p>
        ) : (
          <ul>
            {p.to_reinforce.map((r) => (
              <li key={r.objective}>
                {objectiveLabel(r.objective)} ({r.objective}): fallaste{" "}
                <span lang="en">{r.activity_key}</span>.{" "}
                <Link to={`/repasos?objetivo=${encodeURIComponent(r.objective)}`}>Practicar ahora</Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </Page>
  );
}
