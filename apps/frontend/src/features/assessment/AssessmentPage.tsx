import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router";
import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { Button } from "../../components/Button";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Notice } from "../../components/Notice";
import { Page } from "../../components/Page";
import styles from "./Assessment.module.css";

const INTRO: Record<string, string> = {
  initial:
    "El diagnóstico inicial se hace una vez. Sirve para ubicar por dónde empezar y para comparar tu avance después.",
  checkpoint:
    "El checkpoint de la unidad se puede repetir. La primera corrida es la que se compara con el diagnóstico.",
  final: "La comprobación final se compara con el diagnóstico inicial.",
};

/** Inicio de una comprobación: qué es, corridas anteriores y empezar o continuar. */
export function AssessmentPage() {
  const { formId = "" } = useParams();
  const navigate = useNavigate();
  const query = useQuery({
    queryKey: ["assessment", formId],
    queryFn: () => unwrap(api.GET("/api/v1/assessments/{form_id}", { params: { path: { form_id: formId } } })),
    retry: false,
  });
  const start = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/assessments/{form_id}/start", {
          params: { path: { form_id: formId }, header: { "Idempotency-Key": newIdempotencyKey() } },
        }),
      ),
    onSuccess: (run) => navigate(`/corridas/${run.id}`),
  });

  if (query.isPending) return <Page title="Comprobación">Cargando…</Page>;
  if (query.isError) {
    return (
      <Page title="No encontramos esta comprobación">
        <ErrorNotice error={query.error} />
        <Link to="/ruta">Ir a la ruta</Link>
      </Page>
    );
  }
  const form = query.data;
  const submitted = form.runs.filter((r) => r.status === "submitted");
  return (
    <Page title={form.title}>
      {form.unit ? <p className={styles.unit}>{form.unit.title}</p> : null}
      <Notice tone="info">{form.label}</Notice>
      <p>{INTRO[form.form_kind ?? "checkpoint"]}</p>
      {form.duration_minutes ? <p>Duración aproximada: {form.duration_minutes} minutos. Sin pistas ni apoyos.</p> : null}
      <p>Tus respuestas se guardan al pasar a la siguiente pregunta; los resultados aparecen al enviar.</p>

      {submitted.length ? (
        <section aria-labelledby="runs">
          <h2 id="runs">Tus corridas</h2>
          <ul className={styles.runs}>
            {submitted.map((r) => (
              <li key={r.id}>
                <Link to={`/corridas/${r.id}`}>
                  Corrida {r.run_number}
                  {r.comparable ? " (la comparable)" : ""}: ver resultados
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <ErrorNotice error={start.error} />
      <div className={styles.actions}>
        {form.open_run_id ? (
          <Button onClick={() => navigate(`/corridas/${form.open_run_id}`)}>Continuar la corrida</Button>
        ) : form.can_start ? (
          <Button onClick={() => start.mutate()} busy={start.isPending}>
            {submitted.length ? "Empezar otra corrida" : "Empezar"}
          </Button>
        ) : (
          <Notice tone="info">Ya hiciste el diagnóstico. Si necesitas repetirlo, pídeselo al equipo.</Notice>
        )}
      </div>
    </Page>
  );
}
