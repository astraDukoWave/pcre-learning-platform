import { Highlight } from "../../components/Highlight";
import { MarginNote } from "../../components/MarginNote";
import type { Activity, ChoiceData, ShownResult } from "./types";

/** La corrección sobre las propias palabras del alumno: su elección resaltada y la nota al
 * margen. Los errores de aprendizaje van en morado ("Revisa esto"), nunca en rojo. */
export function Feedback({ activity, shown }: { activity: Activity; shown: ShownResult }) {
  if (activity.format === "choice") {
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
          {shown.aided ? <p>Lo resolviste con ayuda; en el repaso intenta sin ella.</p> : null}
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
  return null;
}
