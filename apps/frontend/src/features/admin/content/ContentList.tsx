import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { api, unwrap } from "../../../api/client";
import { Button } from "../../../components/Button";
import { ErrorNotice } from "../../../components/ErrorNotice";
import { Notice } from "../../../components/Notice";
import { Page } from "../../../components/Page";
import styles from "../admin.module.css";
import { KIND_LABEL, STATUS_LABEL } from "./types";

/** Panel editorial (REQ-08): revisiones con filtros por tipo, estado y unidad, y publicar en
 * lote lo aprobado de una unidad. Publicar es siempre una acción humana. */
export function ContentList() {
  const qc = useQueryClient();
  const [kind, setKind] = useState("");
  const [status, setStatus] = useState("");
  const [unit, setUnit] = useState("");
  const units = useQuery({ queryKey: ["admin-units"], queryFn: () => unwrap(api.GET("/api/v1/admin/content/units")) });
  const rows = useQuery({
    queryKey: ["admin-revisions", kind, status, unit],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/admin/content/revisions", {
          params: { query: { kind: kind || undefined, status: status || undefined, unit_id: unit || undefined } },
        }),
      ),
  });
  const publishUnit = useMutation({
    mutationFn: (unitId: string) =>
      unwrap(api.POST("/api/v1/admin/content/units/{unit_id}/publish", { params: { path: { unit_id: unitId } } })),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["admin-revisions"] }),
  });
  const selectedUnit = units.data?.find((u) => u.id === unit);
  return (
    <Page title="Contenido" wide>
      <div className={styles.filters}>
        <label>
          Tipo
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="">Todos</option>
            {Object.entries(KIND_LABEL).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label>
          Estado
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Todos</option>
            {Object.entries(STATUS_LABEL).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label>
          Unidad
          <select value={unit} onChange={(e) => setUnit(e.target.value)}>
            <option value="">Todas</option>
            {units.data?.map((u) => (
              <option key={u.id} value={u.id}>
                {u.position}. {u.title}
              </option>
            ))}
          </select>
        </label>
        {selectedUnit ? (
          <Button variant="secondary" busy={publishUnit.isPending} onClick={() => publishUnit.mutate(selectedUnit.id)}>
            Publicar lo aprobado de la unidad
          </Button>
        ) : null}
      </div>
      <ErrorNotice error={rows.error ?? publishUnit.error} />
      {publishUnit.data ? (
        <Notice tone="success">
          {publishUnit.data.length
            ? `Publicadas: ${publishUnit.data.map((p) => `${p.item_slug} v${p.version}`).join(", ")}.`
            : "No había revisiones aprobadas en la unidad."}
        </Notice>
      ) : null}
      {rows.isPending ? <p>Cargando…</p> : null}
      {rows.data ? (
        <table className={styles.table}>
          <caption className="visually-hidden">Revisiones de contenido</caption>
          <thead>
            <tr>
              <th scope="col">Ítem</th>
              <th scope="col">Tipo</th>
              <th scope="col">Versión</th>
              <th scope="col">Estado</th>
              <th scope="col">Pendientes</th>
            </tr>
          </thead>
          <tbody>
            {rows.data.map((r) => (
              <tr key={r.id}>
                <td>
                  <Link to={`/admin/contenido/${r.id}`}>{r.item_title}</Link>
                  <div className={styles.tag}>{r.item_slug}</div>
                </td>
                <td>{KIND_LABEL[r.kind] ?? r.kind}</td>
                <td>v{r.version}</td>
                <td>
                  {STATUS_LABEL[r.status] ?? r.status}
                  {r.is_published ? " · en línea" : ""}
                </td>
                <td>
                  {r.audio_pending ? <div className={styles.warn}>Audio sin revisar</div> : null}
                  {r.open_material_findings ? (
                    <div className={styles.warn}>{r.open_material_findings} hallazgos materiales</div>
                  ) : null}
                  {r.warnings ? <div>{r.warnings} advertencias</div> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </Page>
  );
}
