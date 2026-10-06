import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router";
import { api, unwrap } from "../../../api/client";
import { Button } from "../../../components/Button";
import { ErrorNotice } from "../../../components/ErrorNotice";
import { Notice } from "../../../components/Notice";
import { Page } from "../../../components/Page";
import styles from "../admin.module.css";
import { AuthorView } from "./AuthorView";
import { StudentPreview } from "./StudentPreview";
import { KIND_LABEL, STATUS_LABEL, type RevisionDetail as Detail } from "./types";

type Tab = "practice" | "assessment" | "author" | "sources" | "findings";
const TABS: { id: Tab; label: string }[] = [
  { id: "practice", label: "Vista de alumno" },
  { id: "assessment", label: "Vista en comprobación" },
  { id: "author", label: "Vista de autor" },
  { id: "sources", label: "Fuentes y lint" },
  { id: "findings", label: "Hallazgos y bitácora" },
];

/** Detalle de una revisión (REQ-08): aprobar muestra el hash; publicar y retirar son
 * acciones humanas; los bloqueos vienen del servidor. */
export function RevisionDetail() {
  const { revisionId = "" } = useParams();
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("practice");
  const [reason, setReason] = useState("");
  const key = ["admin-revision", revisionId];
  const detail = useQuery({
    queryKey: key,
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/admin/content/revisions/{revision_id}", { params: { path: { revision_id: revisionId } } }),
      ),
  });
  const refresh = (data: Detail) => {
    qc.setQueryData(key, data);
    void qc.invalidateQueries({ queryKey: ["admin-revisions"] });
  };
  const path = { params: { path: { revision_id: revisionId } } };
  const approve = useMutation({
    mutationFn: (hash: string) =>
      unwrap(api.POST("/api/v1/admin/content/revisions/{revision_id}/approve", { ...path, body: { content_hash: hash } })),
    onSuccess: refresh,
  });
  const publish = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/admin/content/revisions/{revision_id}/publish", { ...path, body: {} })),
    onSuccess: refresh,
  });
  const withdraw = useMutation({
    mutationFn: () =>
      unwrap(api.POST("/api/v1/admin/content/revisions/{revision_id}/withdraw", { ...path, body: { reason } })),
    onSuccess: refresh,
  });

  if (detail.isPending) return <Page title="Revisión">Cargando…</Page>;
  if (detail.isError) {
    return (
      <Page title="Revisión">
        <ErrorNotice error={detail.error} />
      </Page>
    );
  }
  const d = detail.data;
  const item = d.item as { title: string; kind: string; slug: string };
  const error = approve.error ?? publish.error ?? withdraw.error;
  const approveBlockers = d.blockers.approve ?? [];
  const publishBlockers = d.blockers.publish ?? [];

  function submitWithdraw(e: FormEvent) {
    e.preventDefault();
    withdraw.mutate();
  }

  return (
    <Page title={`${item.title} · v${d.version}`} wide>
      <p>
        <Link to="/admin/contenido">← Contenido</Link>
      </p>
      <p>
        {KIND_LABEL[item.kind] ?? item.kind} · <span className={styles.tag}>{item.slug}</span> · Estado:{" "}
        <strong>{STATUS_LABEL[d.status] ?? d.status}</strong>
      </p>
      <p className={styles.mono}>
        Hash: {d.content_hash}
        {d.approved_hash ? `\nAprobado: ${d.approved_hash}` : ""}
        {`\nArchivo: ${d.source_path}${d.source_commit ? ` @ ${d.source_commit.slice(0, 7)}` : ""}`}
      </p>
      {d.withdraw_reason ? <Notice tone="info">Retirada: {d.withdraw_reason}</Notice> : null}
      <ErrorNotice error={error} />

      <div className={styles.actions}>
        {d.status === "draft" ? (
          approveBlockers.length ? (
            <Notice tone="note" title="No se puede aprobar todavía">
              <ul>
                {approveBlockers.map((b) => (
                  <li key={b}>{b}</li>
                ))}
              </ul>
            </Notice>
          ) : (
            <Button onClick={() => approve.mutate(d.content_hash)} busy={approve.isPending}>
              Aprobar el hash {d.content_hash.slice(0, 12)}…
            </Button>
          )
        ) : null}
        {d.status === "approved" ? (
          publishBlockers.length ? (
            <Notice tone="note" title="No se puede publicar todavía">
              <ul>
                {publishBlockers.map((b) => (
                  <li key={b}>{b}</li>
                ))}
              </ul>
            </Notice>
          ) : (
            <Button onClick={() => publish.mutate()} busy={publish.isPending}>
              Publicar esta revisión
            </Button>
          )
        ) : null}
      </div>
      {d.status === "published" ? (
        <form className={styles.form} onSubmit={submitWithdraw}>
          <label>
            Motivo para retirar (bloquea intentos nuevos; el historial se conserva)
            <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} maxLength={2000} />
          </label>
          <Button type="submit" variant="secondary" busy={withdraw.isPending} disabled={!reason.trim()}>
            Retirar
          </Button>
        </form>
      ) : null}

      <div className={styles.tabs} role="tablist" aria-label="Secciones de la revisión">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            id={`tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls={`panel-${t.id}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <section role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === "practice" ? <StudentPreview preview={d.preview_practice} /> : null}
        {tab === "assessment" ? <StudentPreview preview={d.preview_assessment} /> : null}
        {tab === "author" ? <AuthorView activities={d.activities} /> : null}
        {tab === "sources" ? <SourcesAndLint detail={d} /> : null}
        {tab === "findings" ? <Findings detail={d} /> : null}
      </section>
    </Page>
  );
}

function SourcesAndLint({ detail }: { detail: Detail }) {
  return (
    <>
      <h3>Advertencias del lint</h3>
      {detail.lint_warnings.length ? (
        <ul>
          {detail.lint_warnings.map((w, i) => (
            <li key={i}>
              <span className={styles.tag}>{String(w.code)}</span> {String(w.message)}
              {w.activity ? ` (${String(w.activity)})` : ""}
            </li>
          ))}
        </ul>
      ) : (
        <p>Sin advertencias.</p>
      )}
      <h3>Fuentes</h3>
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">Fuente</th>
            <th scope="col">Afirmación</th>
            <th scope="col">Alcance</th>
            <th scope="col">Estado</th>
          </tr>
        </thead>
        <tbody>
          {detail.sources.map((s, i) => (
            <tr key={i}>
              <td>
                <a href={String(s.url)} rel="noreferrer noopener" target="_blank">
                  {String(s.title)}
                </a>{" "}
                ({String(s.publisher)})
              </td>
              <td>{String(s.claim)}</td>
              <td>{String(s.scope)}</td>
              <td className={s.status === "pending" ? styles.warn : undefined}>
                {s.status === "pending" ? "pendiente de consultar" : `consultada ${String(s.accessed_on)}`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <h3>Lista de revisión</h3>
      <ul>
        {detail.checklist.map((c) => (
          <li key={c}>{c}</li>
        ))}
      </ul>
    </>
  );
}

function Findings({ detail }: { detail: Detail }) {
  const qc = useQueryClient();
  const [category, setCategory] = useState("");
  const [severity, setSeverity] = useState<"material" | "minor">("minor");
  const [description, setDescription] = useState("");
  const add = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/admin/content/revisions/{revision_id}/findings", {
          params: { path: { revision_id: detail.id } },
          body: { category, severity, description },
        }),
      ),
    onSuccess: () => {
      setCategory("");
      setDescription("");
      void qc.invalidateQueries({ queryKey: ["admin-revision", detail.id] });
    },
  });
  const resolve = useMutation({
    mutationFn: (id: string) =>
      unwrap(
        api.PATCH("/api/v1/admin/content/findings/{finding_id}", {
          params: { path: { finding_id: id } },
          body: { status: "resolved" },
        }),
      ),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["admin-revision", detail.id] }),
  });
  return (
    <>
      <h3>Hallazgos</h3>
      <ErrorNotice error={add.error ?? resolve.error} />
      {detail.findings.length ? (
        <ul>
          {detail.findings.map((f) => (
            <li key={f.id}>
              <span className={f.severity === "material" ? styles.warn : undefined}>{f.severity}</span> ·{" "}
              {f.category}: {f.description} · <em>{f.status}</em>{" "}
              {f.status === "open" ? (
                <Button variant="quiet" onClick={() => resolve.mutate(f.id)}>
                  Marcar resuelto
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p>Sin hallazgos.</p>
      )}
      <form
        className={styles.form}
        onSubmit={(e) => {
          e.preventDefault();
          add.mutate();
        }}
      >
        <label>
          Categoría
          <input value={category} onChange={(e) => setCategory(e.target.value)} maxLength={40} />
        </label>
        <label>
          Severidad
          <select value={severity} onChange={(e) => setSeverity(e.target.value as "material" | "minor")}>
            <option value="minor">Menor</option>
            <option value="material">Material (bloquea aprobar)</option>
          </select>
        </label>
        <label>
          Descripción
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} maxLength={2000} />
        </label>
        <Button type="submit" variant="secondary" busy={add.isPending} disabled={category.length < 2 || description.length < 3}>
          Agregar hallazgo
        </Button>
      </form>
      <h3>Bitácora de decisiones</h3>
      {detail.decisions.length ? (
        <ol>
          {detail.decisions.map((dec, i) => (
            <li key={i}>
              {String(dec.action)} · {String(dec.created_at)}
              {dec.note ? ` · ${String(dec.note)}` : ""}
            </li>
          ))}
        </ol>
      ) : (
        <p>Sin decisiones todavía.</p>
      )}
    </>
  );
}
