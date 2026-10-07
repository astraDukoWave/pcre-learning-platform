import { Highlight } from "../../components/Highlight";
import { AiFeedback } from "../feedback/AiFeedback";
import type { AiFeedback as AiFeedbackData } from "../feedback/aiFeedback";
import { Transcription } from "../feedback/Transcription";
import type { StoredTranscription } from "../feedback/transcription";
import { MarginNote } from "../../components/MarginNote";
import styles from "./Feedback.module.css";
import { SelfAssessment } from "./SelfAssessment";
import type { Activity, AttemptDetail, ChoiceData, Rubric, ShownResult, WordCompletionData } from "./types";

function Aided({ shown }: { shown: ShownResult }) {
  return shown.aided ? <p>Lo resolviste con ayuda; en el repaso intenta sin ella.</p> : null;
}

function ChoiceFeedback({ activity, shown }: { activity: Activity; shown: ShownResult }) {
  const data = activity.data as unknown as ChoiceData;
  const selected = (shown.response.selected as string[] | undefined) ?? [];
  const chosen = data.options.filter((o) => selected.includes(o.id));
  const keys = (shown.result.correct_options as string[] | undefined) ?? [];
  const keyText = data.options.filter((o) => keys.includes(o.id)).map((o) => o.text);
  const why = (shown.result.option_feedback as Record<string, string> | undefined) ?? {};
  if (shown.correct) {
    return (
      <MarginNote tone="ok" title="Correcto">
        {shown.explanation ? <p>{shown.explanation}</p> : null}
        <Aided shown={shown} />
      </MarginNote>
    );
  }
  return (
    <MarginNote title="Revisa esto">
      <p>
        Elegiste:{" "}
        {chosen.map((o) => (
          <Highlight key={o.id}>
            <span lang="en">{o.text}</span>
          </Highlight>
        ))}
      </p>
      {chosen.map((o) => (why[o.id] ? <p key={o.id}>{why[o.id]}</p> : null))}
      {shown.explanation ? <p>{shown.explanation}</p> : null}
      <p>
        La respuesta correcta: <span lang="en">{keyText.join(" · ")}</span>
      </p>
    </MarginNote>
  );
}

function WordCompletionFeedback({ activity, shown }: { activity: Activity; shown: ShownResult }) {
  const data = activity.data as unknown as WordCompletionData;
  const perGap = (shown.result.per_gap as Record<string, boolean> | undefined) ?? {};
  const accepted = (shown.result.accepted as Record<string, string[]> | undefined) ?? {};
  const answers = (shown.response.answers as Record<string, string> | undefined) ?? {};
  if (shown.correct) {
    return (
      <MarginNote tone="ok" title="Correcto">
        {shown.explanation ? <p>{shown.explanation}</p> : null}
        <Aided shown={shown} />
      </MarginNote>
    );
  }
  return (
    <MarginNote title="Revisa esto">
      <ul>
        {data.gaps.map((g, i) =>
          perGap[g.id] ? null : (
            <li key={g.id}>
              Hueco {i + 1}: escribiste{" "}
              <Highlight>
                <span lang="en">{answers[g.id] || "—"}</span>
              </Highlight>
              ; se acepta: <span lang="en">{(accepted[g.id] ?? []).join(" · ")}</span>
            </li>
          ),
        )}
      </ul>
      {shown.explanation ? <p>{shown.explanation}</p> : null}
    </MarginNote>
  );
}

function OrderFeedback({ shown }: { shown: ShownResult }) {
  const order = (shown.response.order as string[] | undefined) ?? [];
  const key = (shown.result.correct_order as string[] | undefined) ?? [];
  if (shown.correct) {
    return (
      <MarginNote tone="ok" title="Correcto">
        {shown.explanation ? <p>{shown.explanation}</p> : null}
        <Aided shown={shown} />
      </MarginNote>
    );
  }
  return (
    <MarginNote title="Revisa esto">
      <p>
        Tu orden:{" "}
        <Highlight>
          <span lang="en">{order.join(" ")}</span>
        </Highlight>
      </p>
      {shown.explanation ? <p>{shown.explanation}</p> : null}
      <p>
        Un orden correcto: <span lang="en">{key.join(" ")}</span>
      </p>
    </MarginNote>
  );
}

function DialogueFeedback({ shown }: { shown: ShownResult }) {
  const turns = (shown.result.turns as { good: boolean }[] | undefined) ?? [];
  const good = turns.filter((t) => t.good).length;
  return (
    <MarginNote tone={shown.correct ? "ok" : "note"} title={shown.correct ? "Lo lograste" : "Revisa esto"}>
      <p>
        {good} de {turns.length} respuestas fueron adecuadas para la situación.
        {shown.correct ? " Conseguiste lo que buscabas." : " Aún no conseguiste lo que buscabas: vuelve a intentarlo."}
      </p>
      {shown.explanation ? <p>{shown.explanation}</p> : null}
      <p>Cada respuesta tiene su nota en la conversación.</p>
    </MarginNote>
  );
}

function ProductionFeedback({
  activity,
  shown,
  onUpdate,
}: {
  activity: Activity;
  shown: ShownResult;
  onUpdate: (detail: AttemptDetail) => void;
}) {
  const fb = shown.feedback;
  const rubric = (fb?.rubric ?? null) as Rubric | null;
  const marks = (shown.result.self_assessment as Record<string, number> | undefined) ?? {};
  const writing = activity.format === "short_writing";
  const pending = shown.evaluation_status === "pending";
  const notEvaluable = shown.evaluation_status === "not_evaluable";
  return (
    <MarginNote title={writing ? "Tu texto se guardó" : "Tu respuesta se guardó"}>
      {writing ? (
        <p>
          {String(shown.result.words ?? 0)} palabras ·{" "}
          {shown.result.within_limits ? "dentro del rango pedido" : "fuera del rango pedido"}.
        </p>
      ) : null}
      {notEvaluable ? <p>No se evaluó porque no hubo grabación. Puedes intentarlo de nuevo cuando quieras.</p> : null}
      {writing && shown.id ? (
        <AiFeedback
          attemptId={shown.id}
          text={String(shown.response.text ?? "")}
          stored={(shown.result.ai_feedback as AiFeedbackData | undefined) ?? null}
          onSaved={onUpdate}
        />
      ) : null}
      {!writing && !notEvaluable && shown.id ? (
        <Transcription
          attemptId={shown.id}
          activityId={activity.id}
          stored={(shown.result.transcription as StoredTranscription | undefined) ?? null}
          aiFeedback={(shown.result.ai_feedback as AiFeedbackData | undefined) ?? null}
          onSaved={onUpdate}
        />
      ) : null}
      {pending && rubric && shown.id ? (
        <SelfAssessment attemptId={shown.id} rubric={rubric} onSaved={onUpdate} />
      ) : null}
      {pending && !rubric ? <p>Cargando la rúbrica…</p> : null}
      {!pending && rubric && Object.keys(marks).length ? (
        <p>
          Tu autoevaluación:{" "}
          {rubric.criteria
            .filter((c) => marks[c.id] !== undefined)
            .map((c) => `${c.name_es} ${marks[c.id]}/3`)
            .join(" · ")}
          . Es tuya, no una calificación.
        </p>
      ) : null}
      {!pending && fb ? (
        <>
          <p>
            <strong>Ejemplo comentado</strong>
          </p>
          {fb.target_sentence ? (
            <p>
              Oración: <span lang="en">{fb.target_sentence}</span>
            </p>
          ) : null}
          {fb.model_answer ? (
            <blockquote lang="en" className={styles.model}>
              {fb.model_answer}
            </blockquote>
          ) : null}
          {fb.model_commentary_es ? <p>{fb.model_commentary_es}</p> : null}
        </>
      ) : null}
    </MarginNote>
  );
}

/** La corrección sobre las propias palabras del alumno: su respuesta resaltada y la nota al
 * margen. Los errores de aprendizaje van en morado ("Revisa esto"), nunca en rojo. */
export function Feedback({
  activity,
  shown,
  onUpdate,
}: {
  activity: Activity;
  shown: ShownResult;
  onUpdate: (detail: AttemptDetail) => void;
}) {
  switch (activity.format) {
    case "choice":
      return <ChoiceFeedback activity={activity} shown={shown} />;
    case "word_completion":
      return <WordCompletionFeedback activity={activity} shown={shown} />;
    case "sentence_order":
      return <OrderFeedback shown={shown} />;
    case "guided_dialogue":
      return <DialogueFeedback shown={shown} />;
    case "short_writing":
    case "recorded_speaking":
      return <ProductionFeedback activity={activity} shown={shown} onUpdate={onUpdate} />;
    default:
      return null;
  }
}
