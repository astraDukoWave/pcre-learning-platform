import { useEffect, useRef } from "react";
import { Button } from "../../../components/Button";
import type { DialogueNode, GuidedDialogueData } from "../../lesson/types";
import styles from "./GuidedDialogueRenderer.module.css";

export interface DialogueWalk {
  turns: { node: DialogueNode; choice: { id: string; text: string } | null }[];
  current: DialogueNode | null;
  finished: boolean;
}

/** Recorre el grafo con el camino elegido (`nodo.opción`). Termina en un nodo sin opciones
 * o en una opción sin `next`. */
export function walk(data: GuidedDialogueData, path: string[]): DialogueWalk {
  const nodes = new Map(data.nodes.map((n) => [n.id, n]));
  const turns: DialogueWalk["turns"] = [];
  let current: DialogueNode | null = nodes.get(data.start) ?? null;
  for (const step of path) {
    if (!current) break;
    const [nodeId, optionId] = step.split(".");
    if (nodeId !== current.id) break;
    const option = current.options.find((o) => o.id === optionId);
    if (!option) break;
    turns.push({ node: current, choice: { id: step, text: option.text } });
    current = option.next ? (nodes.get(option.next) ?? null) : null;
  }
  if (current && current.options.length === 0) {
    turns.push({ node: current, choice: null });
    current = null;
  }
  return { turns, current, finished: current === null };
}

export interface GuidedDialogueRendererProps {
  data: GuidedDialogueData;
  path: string[];
  onChange: (path: string[]) => void;
  disabled: boolean;
  turnFeedback?: Record<string, { feedback_es: string; good: boolean }> | null;
}

/** Conversación por turnos: la otra persona dice una línea y eliges qué responder. La
 * retroalimentación de cada opción llega del servidor al enviar, junto con el resumen. */
export function GuidedDialogueRenderer({ data, path, onChange, disabled, turnFeedback }: GuidedDialogueRendererProps) {
  const { turns, current, finished } = walk(data, path);
  const firstOption = useRef<HTMLButtonElement>(null);
  const started = path.length > 0;

  useEffect(() => {
    if (started && !disabled) firstOption.current?.focus();
  }, [path.length, started, disabled]);

  return (
    <div className={styles.wrap}>
      <ol className={styles.log} aria-label="Conversación">
        {turns.map(({ node, choice }, i) => {
          const note = choice ? turnFeedback?.[choice.id] : undefined;
          return (
            <li key={`${node.id}-${i}`} className={styles.turn}>
              <p className={node.speaker === "narrator" ? styles.narrator : styles.agent} lang="en">
                {node.text_en}
              </p>
              {choice ? (
                <div className={styles.mine}>
                  <p lang="en">
                    <span className="visually-hidden">Tú: </span>
                    {choice.text}
                  </p>
                  {note ? (
                    <p className={note.good ? styles.good : styles.review}>
                      {note.good ? "✓ " : "✎ "}
                      {note.feedback_es}
                    </p>
                  ) : null}
                </div>
              ) : null}
            </li>
          );
        })}
        {current ? (
          <li className={styles.turn}>
            <p className={current.speaker === "narrator" ? styles.narrator : styles.agent} lang="en">
              {current.text_en}
            </p>
          </li>
        ) : null}
      </ol>
      {current && !disabled ? (
        <fieldset className={styles.options}>
          <legend>¿Qué respondes?</legend>
          {current.options.map((o, i) => (
            <button
              key={o.id}
              ref={i === 0 ? firstOption : undefined}
              type="button"
              className={styles.option}
              onClick={() => onChange([...path, `${current.id}.${o.id}`])}
              lang="en"
            >
              {o.text}
            </button>
          ))}
        </fieldset>
      ) : null}
      {finished && !disabled ? <p aria-live="polite">La conversación terminó. Envíala para ver cómo te fue.</p> : null}
      {started && !disabled ? (
        <Button variant="quiet" onClick={() => onChange([])}>
          Empezar la conversación de nuevo
        </Button>
      ) : null}
    </div>
  );
}
