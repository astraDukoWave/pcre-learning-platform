import { api, unwrap } from "../../api/client";
import type { components } from "../../api/schema";
import type { Recording } from "../activities/recorded-speaking/recordings";

export type Transcription = components["schemas"]["TranscriptionOut"];
type Form = { attempt_id: string; activity_id: string; duration_ms: number; audio: string };

/** Límites de REQ-04, iguales a los del servidor. */
export const MAX_SECONDS = 60;
export const MAX_BYTES = 2 * 1024 * 1024;

export function canTranscribe(recording: Recording): boolean {
  return recording.durationMs <= MAX_SECONDS * 1000 && recording.blob.size <= MAX_BYTES;
}

/** Lo que guarda el intento (`result.transcription`): la misma vista sin `attempt_id`. */
export type StoredTranscription = Omit<Transcription, "attempt_id">;

/** Envía la grabación en memoria (`multipart/form-data`); el navegador pone el `boundary`.
 * El servidor la transcribe y la descarta (REQ-04). */
export function sendRecording(
  attemptId: string,
  activityId: string,
  recording: Recording,
  key: string,
): Promise<Transcription> {
  const form = new FormData();
  form.append("attempt_id", attemptId);
  form.append("activity_id", activityId);
  form.append("duration_ms", String(Math.max(1, Math.round(recording.durationMs))));
  const type = recording.blob.type || "audio/webm";
  form.append("audio", recording.blob, type.startsWith("audio/mp4") ? "grabacion.mp4" : "grabacion.webm");
  return unwrap(
    api.POST("/api/v1/speaking/transcriptions", {
      params: { header: { "Idempotency-Key": key } },
      body: form as unknown as Form,
      bodySerializer: (body) => body as unknown as FormData,
    }),
  );
}
