/** Última grabación de cada actividad, solo en la memoria de esta pestaña: nunca en
 * localStorage, IndexedDB ni el servidor. Se pierde al recargar. Sirve para pedir la
 * transcripción después de enviar (MVP-02 REQ-04); sin pedirla, el audio no sale del equipo. */
export interface Recording {
  blob: Blob;
  durationMs: number;
}

const recordings = new Map<string, Recording>();

export function keepRecording(activityId: string, recording: Recording): void {
  recordings.set(activityId, recording);
}

export function recordingFor(activityId: string): Recording | null {
  return recordings.get(activityId) ?? null;
}

export function forgetRecording(activityId: string): void {
  recordings.delete(activityId);
}
