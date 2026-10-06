import type { ChoiceData } from "../../lesson/types";
import styles from "./ChoiceRenderer.module.css";

export interface ChoiceRendererProps {
  activityId: string;
  data: ChoiceData;
  selected: string[];
  onChange: (selected: string[]) => void;
  disabled: boolean;
  correctOptions?: string[] | null;
  legend: string;
}

/** Radios (una respuesta) o casillas (varias); elementos nativos, operables con teclado. */
export function ChoiceRenderer({ activityId, data, selected, onChange, disabled, correctOptions, legend }: ChoiceRendererProps) {
  const multiple = Boolean(data.multiple);
  function toggle(id: string, checked: boolean) {
    if (!multiple) {
      onChange([id]);
      return;
    }
    onChange(checked ? [...selected, id] : selected.filter((x) => x !== id));
  }
  return (
    <fieldset className={styles.group} disabled={disabled}>
      <legend className="visually-hidden">{legend}</legend>
      {data.options.map((option) => {
        const chosen = selected.includes(option.id);
        const isKey = correctOptions?.includes(option.id) ?? false;
        const state = correctOptions ? (isKey ? styles.key : chosen ? styles.missed : "") : "";
        return (
          <label key={option.id} className={[styles.option, chosen ? styles.chosen : "", state].join(" ")}>
            <input
              type={multiple ? "checkbox" : "radio"}
              name={`activity-${activityId}`}
              value={option.id}
              checked={chosen}
              onChange={(e) => toggle(option.id, e.target.checked)}
            />
            <span lang="en">{option.text}</span>
            {correctOptions && isKey ? <span className={styles.badge}>Respuesta correcta</span> : null}
          </label>
        );
      })}
    </fieldset>
  );
}
