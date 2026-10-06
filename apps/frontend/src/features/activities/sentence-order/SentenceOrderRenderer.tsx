import { useId, useState, type KeyboardEvent } from "react";
import { Button } from "../../../components/Button";
import type { SentenceOrderData } from "../../lesson/types";
import styles from "./SentenceOrderRenderer.module.css";

export interface SentenceOrderRendererProps {
  data: SentenceOrderData;
  order: string[];
  onChange: (order: string[]) => void;
  disabled: boolean;
}

/** Índices de las fichas colocadas; una ficha repetida ("the" dos veces) se distingue por
 * su posición en el banco. */
function placedIndices(tokens: string[], order: string[]): number[] {
  const used = new Set<number>();
  const out: number[] = [];
  for (const word of order) {
    const i = tokens.findIndex((t, j) => t === word && !used.has(j));
    if (i === -1) continue;
    used.add(i);
    out.push(i);
  }
  return out;
}

/** Fichas que se tocan para armar la oración. Alternativa de teclado: seleccionar una
 * ficha colocada y moverla con las flechas (o con los botones), Suprimir la quita. */
export function SentenceOrderRenderer({ data, order, onChange, disabled }: SentenceOrderRendererProps) {
  const uid = useId();
  const tokens = data.tokens;
  const placed = placedIndices(tokens, order);
  const [selected, setSelected] = useState<number | null>(null);
  const [status, setStatus] = useState("");

  const word = (i: number | undefined) => (i === undefined ? "" : (tokens[i] ?? ""));

  function commit(next: number[], sel: number | null, message: string) {
    onChange(next.map((i) => word(i)));
    setSelected(sel);
    setStatus(message);
  }

  function add(i: number) {
    const next = [...placed, i];
    commit(next, null, `«${word(i)}» en la posición ${next.length} de ${tokens.length}.`);
  }

  function move(pos: number, delta: number) {
    const target = pos + delta;
    const a = placed[pos];
    const b = placed[target];
    if (a === undefined || b === undefined) return;
    const next = [...placed];
    next[pos] = b;
    next[target] = a;
    commit(next, target, `«${word(a)}» en la posición ${target + 1} de ${next.length}.`);
  }

  function remove(pos: number) {
    const removed = word(placed[pos]);
    commit(
      placed.filter((_, j) => j !== pos),
      null,
      `«${removed}» volvió a las fichas.`,
    );
  }

  function onKey(e: KeyboardEvent<HTMLButtonElement>, pos: number) {
    if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      e.preventDefault();
      move(pos, -1);
    } else if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      e.preventDefault();
      move(pos, 1);
    } else if (e.key === "Delete" || e.key === "Backspace") {
      e.preventDefault();
      remove(pos);
    }
  }

  return (
    <div className={styles.wrap}>
      <p className={styles.label} id={`${uid}-answer`}>
        Tu oración
      </p>
      <ol className={styles.answer} aria-labelledby={`${uid}-answer`}>
        {placed.length === 0 ? <li className={styles.empty}>Toca las fichas en orden.</li> : null}
        {placed.map((i, pos) => (
          <li key={`${i}-${pos}`}>
            <button
              type="button"
              className={[styles.token, styles.placed, selected === pos ? styles.selected : ""].join(" ")}
              aria-pressed={selected === pos}
              aria-label={`${word(i)}, posición ${pos + 1}`}
              disabled={disabled}
              onClick={() => setSelected(selected === pos ? null : pos)}
              onKeyDown={(e) => onKey(e, pos)}
              lang="en"
            >
              {word(i)}
            </button>
          </li>
        ))}
      </ol>
      {selected !== null && !disabled ? (
        <div className={styles.controls} role="group" aria-label="Mover la ficha seleccionada">
          <Button variant="secondary" onClick={() => move(selected, -1)} disabled={selected === 0}>
            ← Mover antes
          </Button>
          <Button variant="secondary" onClick={() => move(selected, 1)} disabled={selected === placed.length - 1}>
            Mover después →
          </Button>
          <Button variant="quiet" onClick={() => remove(selected)}>
            Quitar
          </Button>
        </div>
      ) : null}
      <p className={styles.label} id={`${uid}-bank`}>
        Fichas
      </p>
      <ul className={styles.bank} aria-labelledby={`${uid}-bank`}>
        {tokens.map((t, i) =>
          placed.includes(i) ? null : (
            <li key={i}>
              <button type="button" className={styles.token} disabled={disabled} onClick={() => add(i)} lang="en">
                {t}
              </button>
            </li>
          ),
        )}
      </ul>
      {placed.length > 0 && !disabled ? (
        <Button variant="quiet" onClick={() => commit([], null, "Empezaste de nuevo.")}>
          Empezar de nuevo
        </Button>
      ) : null}
      <p className="visually-hidden" aria-live="polite">
        {status}
      </p>
    </div>
  );
}
