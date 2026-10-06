import { useState, type FormEvent } from "react";
import { Button } from "../../components/Button";
import { Field } from "../../components/Field";
import type { Me } from "../auth/session";
import styles from "./GoalForm.module.css";
import {
  EXAMS,
  LEVELS,
  PURPOSES,
  detectedTimezone,
  timezones,
  type GoalPurpose,
  type SelfLevel,
  type TargetExam,
} from "./options";

export interface GoalValues {
  display_name: string | null;
  goal_purpose: GoalPurpose;
  target_exam: TargetExam;
  target_exam_other: string | null;
  target_score: string | null;
  target_date: string | null;
  self_reported_level: SelfLevel;
  timezone: string;
}

export function initialGoal(me: Me): GoalValues {
  return {
    display_name: me.display_name ?? null,
    goal_purpose: me.goal_purpose ?? "unknown",
    target_exam: me.target_exam ?? "unknown",
    target_exam_other: me.target_exam_other ?? null,
    target_score: me.target_score ?? null,
    target_date: me.target_date ?? null,
    self_reported_level: me.self_reported_level ?? "unknown",
    timezone: me.onboarded ? me.timezone : detectedTimezone(),
  };
}

export function GoalForm({
  me,
  submitLabel,
  busy,
  onSubmit,
}: {
  me: Me;
  submitLabel: string;
  busy: boolean;
  onSubmit: (values: GoalValues) => void;
}) {
  const [values, setValues] = useState<GoalValues>(() => initialGoal(me));
  const set = <K extends keyof GoalValues>(key: K, value: GoalValues[K]) =>
    setValues((v) => ({ ...v, [key]: value }));

  function submit(e: FormEvent) {
    e.preventDefault();
    onSubmit({
      ...values,
      target_exam_other: values.target_exam === "other" ? values.target_exam_other : null,
    });
  }

  return (
    <form onSubmit={submit} className={styles.form}>
      <Field
        label="Cómo quieres que te llamemos (opcional)"
        value={values.display_name ?? ""}
        maxLength={80}
        onChange={(e) => set("display_name", e.target.value || null)}
      />
      <fieldset className={styles.group}>
        <legend>¿Para qué necesitas el inglés?</legend>
        {PURPOSES.map((p) => (
          <label key={p.value} className={styles.option}>
            <input
              type="radio"
              name="goal_purpose"
              value={p.value}
              checked={values.goal_purpose === p.value}
              onChange={() => set("goal_purpose", p.value)}
            />
            {p.label}
          </label>
        ))}
      </fieldset>
      <fieldset className={styles.group}>
        <legend>¿Qué examen te piden?</legend>
        {EXAMS.map((x) => (
          <label key={x.value} className={styles.option}>
            <input
              type="radio"
              name="target_exam"
              value={x.value}
              checked={values.target_exam === x.value}
              onChange={() => set("target_exam", x.value)}
            />
            {x.label}
          </label>
        ))}
      </fieldset>
      {values.target_exam === "other" ? (
        <Field
          label="¿Cuál?"
          value={values.target_exam_other ?? ""}
          maxLength={80}
          onChange={(e) => set("target_exam_other", e.target.value || null)}
        />
      ) : null}
      <div className={styles.row}>
        <Field
          label="Puntuación objetivo (opcional)"
          value={values.target_score ?? ""}
          maxLength={20}
          onChange={(e) => set("target_score", e.target.value || null)}
        />
        <Field
          label="Fecha objetivo (opcional)"
          type="date"
          value={values.target_date ?? ""}
          onChange={(e) => set("target_date", e.target.value || null)}
        />
      </div>
      <fieldset className={styles.group}>
        <legend>Tu percepción de tu nivel</legend>
        <p className={styles.hint}>Es solo tu percepción; no es un nivel acreditado.</p>
        {LEVELS.map((l) => (
          <label key={l.value} className={styles.option}>
            <input
              type="radio"
              name="self_reported_level"
              value={l.value}
              checked={values.self_reported_level === l.value}
              onChange={() => set("self_reported_level", l.value)}
            />
            {l.label}
          </label>
        ))}
      </fieldset>
      <label className={styles.select}>
        <span>Tu zona horaria</span>
        <select value={values.timezone} onChange={(e) => set("timezone", e.target.value)}>
          {timezones(values.timezone).map((tz) => (
            <option key={tz} value={tz}>
              {tz}
            </option>
          ))}
        </select>
      </label>
      <Button type="submit" busy={busy}>
        {submitLabel}
      </Button>
    </form>
  );
}
