import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router";
import { useCapabilities } from "../feedback/capabilities";
import { api, unwrap } from "../../api/client";
import { ApiError } from "../../api/errors";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Highlight } from "../../components/Highlight";
import { Notice } from "../../components/Notice";
import { Page } from "../../components/Page";
import { LessonRating } from "../feedback/LessonRating";
import { ActivityCard } from "./ActivityCard";
import styles from "./LessonPage.module.css";
import type { Lesson } from "./types";

function firstUnanswered(lesson: Lesson): number {
  const index = lesson.activities.findIndex((a) => !lesson.last_attempts[a.id]);
  return index === -1 ? lesson.activities.length : index;
}

/** Lección o escenario (modo texto): misma estructura de actividades con estado propio. */
export function LessonPage({ kind = "lesson" }: { kind?: "lesson" | "scenario" }) {
  const capabilities = useCapabilities();
  const { itemId = "" } = useParams();
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ["lesson", itemId],
    queryFn: () =>
      kind === "scenario"
        ? unwrap(
            api.GET("/api/v1/scenarios/{item_id}", {
              params: { path: { item_id: itemId } },
            }),
          )
        : unwrap(
            api.GET("/api/v1/lessons/{item_id}", {
              params: { path: { item_id: itemId } },
            }),
          ),
    retry: false,
  });
  const scenario = kind === "scenario";
  const [index, setIndex] = useState<number | null>(null);
  const [completed, setCompleted] = useState(false);

  if (query.isPending) return <Page title={scenario ? "Escenario" : "Lección"}>Cargando…</Page>;
  if (query.isError) {
    const withdrawn = query.error instanceof ApiError && query.error.code === "lesson_withdrawn";
    return (
      <Page
        title={
          withdrawn
            ? scenario
              ? "Escenario retirado"
              : "Lección retirada"
            : scenario
              ? "No encontramos este escenario"
              : "No encontramos esta lección"
        }
      >
        {withdrawn ? <Notice tone="info">{query.error.message}</Notice> : <ErrorNotice error={query.error} />}
        <Link to="/ruta">Ir a la ruta</Link>
      </Page>
    );
  }
  const lesson = query.data;
  const total = lesson.activities.length;
  const current = index ?? firstUnanswered(lesson);
  const done = completed || Boolean(lesson.progress.completed_at);
  const activity = lesson.activities[current];
  const passages = lesson.passages ?? [];

  return (
    <Page title={lesson.title} wide>
      <p className={styles.unit}>{lesson.unit?.title}</p>
      {lesson.notice ? <Notice tone="info">{lesson.notice}</Notice> : null}
      {lesson.objective_es ? <p>{lesson.objective_es}</p> : null}
      {scenario ? (
        <section className={styles.scenario} aria-label="Situación">
          <p>{lesson.situation_es}</p>
          {lesson.learner_role_en ? (
            <p>
              Tu papel: <span lang="en">{lesson.learner_role_en}</span>
            </p>
          ) : null}
          {lesson.required_moves?.length ? (
            <>
              <p>Lo que tienes que lograr:</p>
              <ul lang="en">
                {(lesson.required_moves ?? []).map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            </>
          ) : null}
          <p className={styles.not}>Práctica en modo texto. No es una tarea del examen oficial.</p>
          {capabilities.data?.voice ? (
            <p>
              <Link to={`/escenarios/${lesson.id}/voz`}>Practicar este escenario por voz con el coach</Link>
            </p>
          ) : null}
        </section>
      ) : null}
      {lesson.pcre ? (
        <details className={styles.pcre}>
          <summary>Cómo funciona: patrón, concepto, reglas y ejemplos</summary>
          <p>
            <strong>Patrón:</strong>{" "}
            <Highlight animate={false}>
              <span lang="en">{lesson.pcre.pattern}</span>
            </Highlight>
          </p>
          <p>
            <strong>Concepto:</strong> {lesson.pcre.concept}
          </p>
          <ul>
            {lesson.pcre.rules.map((r) => (
              <li key={r.text}>
                {r.text}
                {r.applies_when_not_es ? (
                  <span className={styles.not}> Cuándo no aplica: {r.applies_when_not_es}</span>
                ) : null}
              </li>
            ))}
          </ul>
          <p>
            <strong>Ejemplos:</strong>
          </p>
          <ul>
            {lesson.pcre.examples.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </details>
      ) : null}

      <div className={passages.length ? styles.split : undefined}>
        {passages.length ? (
          <section className={styles.passages} aria-label="Texto">
            {passages
              .filter((p) => !activity || lesson.activities.some((a) => a.stimulus?.passage === p.id))
              .map((p) => (
                <article key={p.id} className={styles.passage} lang="en">
                  {p.title_en ? <h2>{p.title_en}</h2> : null}
                  <p>{p.text_en}</p>
                </article>
              ))}
          </section>
        ) : null}
        <section aria-label="Actividades">
          <nav aria-label="Actividades de la lección" className={styles.stepper}>
            {lesson.activities.map((a, i) => (
              <button
                key={a.id}
                type="button"
                className={[styles.step, i === current ? styles.current : ""].join(" ")}
                aria-current={i === current ? "step" : undefined}
                onClick={() => setIndex(i)}
              >
                {i + 1}
                {lesson.last_attempts[a.id] ? <span aria-label=" (respondida)"> ✓</span> : null}
              </button>
            ))}
          </nav>
          {activity && !(done && index === null) ? (
            <>
              <p className={styles.counter}>
                Actividad {current + 1} de {total}
              </p>
              <ActivityCard
                key={activity.id}
                activity={activity}
                last={lesson.last_attempts[activity.id]}
                isLast={current === total - 1}
                revisionId={lesson.revision_id}
                onSubmitted={(lessonCompleted) => {
                  // Se queda en esta actividad para mostrar el feedback aunque el refresco
                  // de la lección cambie cuál es la primera sin responder.
                  setIndex(current);
                  if (lessonCompleted) setCompleted(true);
                  void qc.invalidateQueries({ queryKey: ["lesson", itemId] });
                }}
                onNext={() => setIndex(current + 1 < total ? current + 1 : total)}
              />
            </>
          ) : (
            <Notice tone="success" title={scenario ? "Completaste el escenario" : "Completaste la lección"}>
              <p>Completar no significa acertar todo: los objetivos que fallaste vuelven en tus repasos.</p>
              <LessonRating itemId={lesson.id} noun={scenario ? "este escenario" : "esta lección"} />
              <p>
                <Link to="/ruta">Volver a la ruta</Link>
              </p>
            </Notice>
          )}
        </section>
      </div>
    </Page>
  );
}
