import { useId } from "react";
import type { ShortWritingData } from "../../lesson/types";
import styles from "./ShortWritingRenderer.module.css";

export function countWords(text: string): number {
  return text.split(/\s+/).filter(Boolean).length;
}

export interface ShortWritingRendererProps {
  data: ShortWritingData;
  text: string;
  onChange: (text: string) => void;
  disabled: boolean;
  label: string;
}

/** Área de texto con contador de palabras. El rango es una guía: fuera de él se puede
 * enviar y el resultado lo indica. */
export function ShortWritingRenderer({ data, text, onChange, disabled, label }: ShortWritingRendererProps) {
  const id = useId();
  const words = countWords(text);
  const within = words >= data.min_words && words <= data.max_words;
  return (
    <div className={styles.wrap}>
      <label htmlFor={id} className="visually-hidden">
        {label}
      </label>
      <textarea
        id={id}
        className={styles.area}
        value={text}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        maxLength={4000}
        rows={9}
        lang="en"
        spellCheck
        aria-describedby={`${id}-count`}
      />
      <p id={`${id}-count`} className={[styles.count, words > 0 && !within ? styles.out : ""].join(" ")}>
        {words} {words === 1 ? "palabra" : "palabras"} · objetivo: entre {data.min_words} y {data.max_words}
      </p>
    </div>
  );
}
