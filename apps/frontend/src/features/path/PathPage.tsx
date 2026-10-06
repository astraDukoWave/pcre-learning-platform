import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api, unwrap } from "../../api/client";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Page } from "../../components/Page";
import { es } from "../../i18n/es";
import styles from "./PathPage.module.css";

const STATE_LABEL: Record<string, string> = {
  not_started: "No iniciada",
  in_progress: "En curso",
  completed: "Completada",
};

const ROUTES: Record<string, string> = { lesson: "/lecciones", scenario: "/escenarios" };

export function usePath() {
  const paths = useQuery({ queryKey: ["paths"], queryFn: () => unwrap(api.GET("/api/v1/learning-paths")) });
  const pathId = paths.data?.[0]?.id;
  const detail = useQuery({
    queryKey: ["path", pathId],
    enabled: Boolean(pathId),
    queryFn: () =>
      unwrap(api.GET("/api/v1/learning-paths/{path_id}", { params: { path: { path_id: pathId ?? "" } } })),
  });
  return { paths, detail };
}

export function PathPage() {
  const { paths, detail } = usePath();
  if (paths.isPending || (paths.data?.length && detail.isPending)) return <Page title="Tu ruta">Cargando…</Page>;
  if (paths.isError || detail.isError) {
    return (
      <Page title="Tu ruta">
        <ErrorNotice error={paths.error ?? detail.error} />
      </Page>
    );
  }
  if (!detail.data) {
    return (
      <Page title="Tu ruta">
        <p>Aún no hay lecciones publicadas. Vuelve pronto.</p>
      </Page>
    );
  }
  const path = detail.data;
  return (
    <Page title="Tu ruta" heading={path.title}>
      <p>
        {path.label} · {es.app.trademark}
      </p>
      {path.units.map((unit) => (
        <section key={unit.id} className={styles.unit} aria-labelledby={`unit-${unit.id}`}>
          <h2 id={`unit-${unit.id}`}>
            Unidad {unit.position} · {unit.title}
          </h2>
          <ul className={styles.items}>
            {unit.items
              .filter((item) => ROUTES[item.kind])
              .map((item) => (
                <li key={item.id} className={styles.item}>
                  <Link to={`${ROUTES[item.kind]}/${item.id}`}>{item.title}</Link>
                  <span className={styles.state}>{STATE_LABEL[item.state]}</span>
                </li>
              ))}
          </ul>
        </section>
      ))}
    </Page>
  );
}
