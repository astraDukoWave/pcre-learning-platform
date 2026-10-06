import { Link } from "react-router";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Notice } from "../../components/Notice";
import { Page } from "../../components/Page";
import { useMe } from "../auth/session";
import { EXAMS, PURPOSES } from "../profile/options";
import { nextActionLink, ratioText, useProgress } from "../progress/useProgress";
import styles from "./HomePage.module.css";

/** Inicio (REQ-09): "Continuar" (lección en curso → repaso vencido → siguiente lección),
 * repasos pendientes, la meta y la invitación al diagnóstico si falta. */
export function HomePage() {
  const me = useMe();
  const progress = useProgress();
  const name = me.data?.display_name;
  const p = progress.data;
  const next = p ? nextActionLink(p.next_action) : null;
  const purpose = PURPOSES.find((x) => x.value === me.data?.goal_purpose)?.label;
  const exam = EXAMS.find((x) => x.value === me.data?.target_exam)?.label;
  return (
    <Page title="Inicio" heading={name ? `Hola, ${name}` : "Inicio"}>
      <ErrorNotice error={progress.error} />
      {p ? (
        <>
          <section className={styles.next} aria-labelledby="next">
            <h2 id="next" className="visually-hidden">
              Qué sigue
            </h2>
            {next ? (
              <Link to={next.to} className={styles.primary}>
                {next.label}
              </Link>
            ) : (
              <p>Completaste todas las lecciones publicadas. Vuelve para tus repasos.</p>
            )}
          </section>
          {p.diagnostic_form_id ? (
            <Notice tone="info" title="Diagnóstico inicial">
              <p>Te dice por dónde empezar y sirve para comparar tu avance después (unos 25 minutos).</p>
              <p>
                <Link to={`/comprobaciones/${p.diagnostic_form_id}`}>Hacer el diagnóstico</Link>
              </p>
            </Notice>
          ) : null}
          <ul className={styles.facts}>
            <li>
              <strong>Repasos pendientes:</strong>{" "}
              {p.reviews_due ? <Link to="/repasos">{p.reviews_due} para hoy</Link> : "ninguno por ahora"}
            </li>
            <li>
              <strong>Avance:</strong> {ratioText(p.advance, " lecciones")}
            </li>
            <li>
              <strong>Racha:</strong>{" "}
              {p.streak_days === 1 ? "1 día" : `${p.streak_days} días`} seguidos con práctica
            </li>
            {purpose || exam ? (
              <li>
                <strong>Tu meta:</strong> {[purpose, exam].filter(Boolean).join(" · ")}
                {me.data?.target_date ? ` · para ${me.data.target_date}` : ""}
              </li>
            ) : null}
          </ul>
          <p>
            <Link to="/progreso">Ver tu progreso</Link>
          </p>
        </>
      ) : progress.isPending ? (
        <p>Cargando…</p>
      ) : null}
      <p>
        <Link to="/ruta">Continuar con tu ruta</Link>
      </p>
    </Page>
  );
}
