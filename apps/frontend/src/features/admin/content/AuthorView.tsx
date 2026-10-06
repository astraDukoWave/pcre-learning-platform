import styles from "../admin.module.css";

interface AuthorActivity {
  id: string;
  key: string;
  format: string;
  task_family: string;
  pool: string;
  objectives: string[];
  prompt: { instructions_es?: string; prompt_en?: string };
  hints: string[];
  support_es: string | null;
  transcript: string | null;
  example: string | null;
  solution: unknown;
  explanation: string | null;
  rubric: { id?: string; version?: number } | null;
}

/** Vista de autor: claves, variantes, explicaciones, ayudas y rúbrica de cada actividad. */
export function AuthorView({ activities }: { activities: Record<string, unknown>[] }) {
  return (
    <div>
      {(activities as unknown as AuthorActivity[]).map((a) => (
        <article key={a.id} className={styles.card} aria-label={a.key}>
          <p>
            <strong>{a.key}</strong> · {a.format} · {a.task_family} · pool {a.pool} · {a.objectives.join(", ")}
          </p>
          {a.prompt.prompt_en ? <p lang="en">{a.prompt.prompt_en}</p> : null}
          <dl>
            <dt>Clave y variantes</dt>
            <dd className={styles.mono}>{JSON.stringify(a.solution, null, 2)}</dd>
            {a.explanation ? (
              <>
                <dt>Explicación</dt>
                <dd>{a.explanation}</dd>
              </>
            ) : null}
            {a.hints.length ? (
              <>
                <dt>Pistas</dt>
                <dd>{a.hints.join(" · ")}</dd>
              </>
            ) : null}
            {a.support_es ? (
              <>
                <dt>Apoyo en español</dt>
                <dd>{a.support_es}</dd>
              </>
            ) : null}
            {a.transcript ? (
              <>
                <dt>Transcripción</dt>
                <dd lang="en">{a.transcript}</dd>
              </>
            ) : null}
            {a.example ? (
              <>
                <dt>Ejemplo</dt>
                <dd lang="en">{a.example}</dd>
              </>
            ) : null}
            {a.rubric ? (
              <>
                <dt>Rúbrica</dt>
                <dd>
                  {a.rubric.id} v{a.rubric.version}
                </dd>
              </>
            ) : null}
          </dl>
        </article>
      ))}
    </div>
  );
}
