import type {
  Activity,
  ChoiceData,
  GuidedDialogueData,
  RecordedSpeakingData,
  SentenceOrderData,
  ShortWritingData,
  WordCompletionData,
} from "../lesson/types";
import { Notice } from "../../components/Notice";
import { ChoiceRenderer } from "./choice/ChoiceRenderer";
import { GuidedDialogueRenderer, walk } from "./guided-dialogue/GuidedDialogueRenderer";
import { RecordedSpeakingRenderer } from "./recorded-speaking/RecordedSpeakingRenderer";
import { SentenceOrderRenderer } from "./sentence-order/SentenceOrderRenderer";
import { ShortWritingRenderer } from "./short-writing/ShortWritingRenderer";
import { WordCompletionRenderer } from "./word-completion/WordCompletionRenderer";

/** ¿La respuesta está completa para enviarse? (el servidor valida igual). */
export function isReady(activity: Activity, response: Record<string, unknown>): boolean {
  switch (activity.format) {
    case "choice":
      return ((response.selected as string[] | undefined) ?? []).length > 0;
    case "word_completion": {
      const answers = (response.answers as Record<string, string> | undefined) ?? {};
      return (activity.data as unknown as WordCompletionData).gaps.every((g) => (answers[g.id] ?? "").trim() !== "");
    }
    case "sentence_order":
      return (
        ((response.order as string[] | undefined) ?? []).length ===
        (activity.data as unknown as SentenceOrderData).tokens.length
      );
    case "short_writing":
      return String(response.text ?? "").trim() !== "";
    case "recorded_speaking":
      return typeof response.recorded === "boolean";
    case "guided_dialogue":
      return walk(activity.data as unknown as GuidedDialogueData, (response.path as string[] | undefined) ?? [])
        .finished;
    default:
      return false;
  }
}

export interface ActivityRendererProps {
  activity: Activity;
  response: Record<string, unknown>;
  onChange: (response: Record<string, unknown>) => void;
  disabled: boolean;
  plays: number;
  onPlay: () => void;
  /** Resultado del servidor, solo después de enviar (marca huecos, opciones y turnos). */
  result?: Record<string, unknown> | null;
}

/** Elige el renderer del formato. Lo usan la lección (práctica) y la corrida (comprobación). */
export function ActivityRenderer({ activity, response, onChange, disabled, plays, onPlay, result }: ActivityRendererProps) {
  const label = activity.prompt_en || activity.instructions_es;
  switch (activity.format) {
    case "choice":
      return (
        <ChoiceRenderer
          activityId={activity.id}
          data={activity.data as unknown as ChoiceData}
          selected={(response.selected as string[] | undefined) ?? []}
          onChange={(next) => onChange({ selected: next })}
          disabled={disabled}
          correctOptions={result ? ((result.correct_options as string[] | undefined) ?? null) : null}
          legend={label}
        />
      );
    case "word_completion":
      return (
        <WordCompletionRenderer
          data={activity.data as unknown as WordCompletionData}
          answers={(response.answers as Record<string, string> | undefined) ?? {}}
          onChange={(answers) => onChange({ answers })}
          disabled={disabled}
          perGap={result ? ((result.per_gap as Record<string, boolean> | undefined) ?? null) : null}
        />
      );
    case "sentence_order":
      return (
        <SentenceOrderRenderer
          data={activity.data as unknown as SentenceOrderData}
          order={(response.order as string[] | undefined) ?? []}
          onChange={(order) => onChange({ order })}
          disabled={disabled}
        />
      );
    case "short_writing":
      return (
        <ShortWritingRenderer
          data={activity.data as unknown as ShortWritingData}
          text={String(response.text ?? "")}
          onChange={(text) => onChange({ text })}
          disabled={disabled}
          label={label}
        />
      );
    case "recorded_speaking":
      return (
        <RecordedSpeakingRenderer
          activityId={activity.id}
          data={activity.data as unknown as RecordedSpeakingData}
          response={response}
          onChange={onChange}
          disabled={disabled}
          plays={plays}
          onPlay={onPlay}
        />
      );
    case "guided_dialogue": {
      const turns = result ? (result.turns as { step: string; feedback_es: string; good: boolean }[] | undefined) : null;
      return (
        <GuidedDialogueRenderer
          data={activity.data as unknown as GuidedDialogueData}
          path={(response.path as string[] | undefined) ?? []}
          onChange={(path) => onChange({ path })}
          disabled={disabled}
          turnFeedback={turns ? Object.fromEntries(turns.map((t) => [t.step, t])) : null}
        />
      );
    }
    default:
      return <Notice tone="info">Este formato todavía no está disponible.</Notice>;
  }
}
