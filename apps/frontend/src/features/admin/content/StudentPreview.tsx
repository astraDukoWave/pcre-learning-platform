import { ActivityRenderer } from "../../activities/ActivityRenderer";
import type { Activity, Passage } from "../../lesson/types";
import styles from "../admin.module.css";

const noop = () => undefined;

/** Vista previa como alumno: el mismo DTO de lista permitida que recibe la persona, con los
 * renderers en solo lectura. No envía nada. */
export function StudentPreview({ preview }: { preview: Record<string, unknown> }) {
  const activities = (preview.activities as Activity[] | undefined) ?? [];
  const passages = (preview.passages as Passage[] | undefined) ?? [];
  return (
    <div>
      <h3>{String(preview.title ?? "")}</h3>
      {preview.objective_es ? <p>{String(preview.objective_es)}</p> : null}
      {preview.situation_es ? <p>{String(preview.situation_es)}</p> : null}
      {passages.map((p) => (
        <article key={p.id} className={styles.card} lang="en">
          {p.title_en ? <h4>{p.title_en}</h4> : null}
          <p className={styles.mono}>{p.text_en}</p>
        </article>
      ))}
      {activities.map((a, i) => (
        <article key={a.id} className={styles.card} aria-label={`Actividad ${i + 1}`}>
          <p>
            <span className={styles.tag}>{a.key}</span> <span className={styles.tag}>{a.pool}</span>{" "}
            {a.aids.length ? `Ayudas anunciadas: ${a.aids.map((x) => `${x.kind} ×${x.count}`).join(", ")}` : "Sin ayudas"}
          </p>
          <p>{a.instructions_es}</p>
          {a.prompt_en ? (
            <p lang="en">
              <strong>{a.prompt_en}</strong>
            </p>
          ) : null}
          {a.stimulus?.text_en ? <blockquote lang="en">{a.stimulus.text_en}</blockquote> : null}
          {a.stimulus?.has_audio ? <p>Audio: {a.stimulus.audio_url ?? "pendiente de revisión"}</p> : null}
          <ActivityRenderer activity={a} response={{}} onChange={noop} disabled plays={0} onPlay={noop} />
        </article>
      ))}
    </div>
  );
}
