import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";
import { api, unwrap } from "../../api/client";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Notice } from "../../components/Notice";
import { Page } from "../../components/Page";
import { objectiveLabel } from "../assessment/types";
import { ActivityCard } from "../lesson/ActivityCard";
import { PROGRESS_KEY } from "../progress/useProgress";
import styles from "./ReviewsPage.module.css";

/** Repasos (REQ-14): uno a la vez, del objetivo vencido más antiguo. Con `?objetivo=`, la
 * reparación inmediata opcional de ese objetivo aunque aún no venza. */
export function ReviewsPage() {
  const [params] = useSearchParams();
  const objective = params.get("objetivo") ?? undefined;
  const qc = useQueryClient();
  const next = useQuery({
    queryKey: ["review-next", objective ?? ""],
    queryFn: () => unwrap(api.GET("/api/v1/me/reviews/next", { params: { query: { objective } } })),
  });
  const list = useQuery({ queryKey: ["reviews"], queryFn: () => unwrap(api.GET("/api/v1/me/reviews")) });

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["review-next"] });
    void qc.invalidateQueries({ queryKey: ["reviews"] });
    void qc.invalidateQueries({ queryKey: PROGRESS_KEY });
  };

  const review = next.data?.review;
  return (
    <Page title="Repasos" wide>
      <ErrorNotice error={next.error ?? list.error} />
      {objective ? (
        <Notice tone="info">
          Práctica inmediata de {objectiveLabel(objective)}: es opcional y no adelanta tu repaso programado.
        </Notice>
      ) : null}
      {next.isPending ? <p>Cargando…</p> : null}
      {next.data && !review ? (
        <Notice tone="success" title={objective ? "No hay ejercicios de repaso para este objetivo" : "No tienes repasos pendientes"}>
          <p>Los repasos vuelven a las 24 horas, a los 3 días y a los 7 días de cada objetivo que fallas.</p>
          <p>
            <Link to="/inicio">Ir al inicio</Link>
          </p>
        </Notice>
      ) : null}
      {review ? (
        <div className={review.passages.length ? styles.split : undefined}>
          {review.passages.length ? (
            <section aria-label="Texto">
              {review.passages.map((p) => (
                <article key={p.id} className={styles.passage} lang="en">
                  {p.title_en ? <h2>{p.title_en}</h2> : null}
                  <p>{p.text_en}</p>
                </article>
              ))}
            </section>
          ) : null}
          <section aria-label="Repaso">
            <p className={styles.meta}>
              {objectiveLabel(review.objective)} · {review.item.title}
              {review.repeated ? " · ya lo respondiste antes: sirve para practicar, no cuenta como repaso diferido" : ""}
            </p>
            {!objective && next.data ? <p>Repasos vencidos: {next.data.remaining_due}</p> : null}
            <ActivityCard
              key={review.activity.id}
              activity={review.activity}
              onSubmitted={() => void qc.invalidateQueries({ queryKey: PROGRESS_KEY })}
              onNext={refresh}
              isLast
              nextLabel="Siguiente repaso"
            />
          </section>
        </div>
      ) : null}
      {list.data && list.data.upcoming.length ? (
        <section aria-labelledby="upcoming">
          <h2 id="upcoming">Próximos repasos</h2>
          <ul>
            {list.data.upcoming.map((r) => (
              <li key={r.objective}>
                {objectiveLabel(r.objective)}: {new Date(r.due_at).toLocaleDateString("es-MX", { dateStyle: "medium" })}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </Page>
  );
}
