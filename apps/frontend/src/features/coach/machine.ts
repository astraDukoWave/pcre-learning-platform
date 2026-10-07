/** Máquina de estados de la pantalla del coach (MVP-02 REQ-06), pura para probarla.
 *
 * intro → connecting → listening ⇄ coach_speaking → ending → ended. Desde cualquier estado
 * activo, un fin del servidor (`ended`) o el cierre del socket llevan a `ended`; la falta de
 * capacidad, de presupuesto, de cupo o de micrófono lleva a `unavailable` con la alternativa
 * en texto. El tiempo restante lo manda el servidor; aquí solo se descuenta para mostrarlo.
 */

export type Phase = "intro" | "connecting" | "listening" | "coach_speaking" | "ending" | "ended" | "unavailable";

export interface Turn {
  n: number;
  role: "coach" | "learner";
  text: string;
  at_s: number;
  aid: boolean;
}

export type EndReason =
  | "deadline"
  | "user_stop"
  | "disconnect"
  | "provider_error"
  | "logout"
  | "silence"
  | "expired"
  | "background"
  | "connection_lost";

export type Unavailable = "disabled" | "budget" | "busy" | "microphone" | "provider" | "existing" | "error";

export interface CoachState {
  phase: Phase;
  sessionId: string | null;
  secondsLeft: number | null;
  warned: boolean;
  turns: Turn[];
  aids: { kind: "repeat" | "slower" | "hint"; text?: string | null }[];
  hint: string | null;
  endReason: EndReason | null;
  durationS: number | null;
  unavailable: Unavailable | null;
  lastError: string | null;
}

export type CoachEvent =
  | { type: "start" }
  | { type: "session_created"; sessionId: string }
  | { type: "create_failed"; code: string }
  | { type: "mic_denied" }
  | { type: "ready"; seconds: number }
  | { type: "agent_speaking" }
  | { type: "agent_done" }
  | { type: "user_started_speaking" }
  | { type: "transcript"; turn: Turn }
  | { type: "aid"; kind: "repeat" | "slower" | "hint" }
  | { type: "hint"; text: string | null }
  | { type: "warning"; secondsLeft: number }
  | { type: "tick" }
  | { type: "stop" }
  | { type: "ended"; reason: EndReason; durationS: number | null }
  | { type: "socket_closed" }
  | { type: "server_error"; code: string }
  | { type: "reset" };

export const initialState: CoachState = {
  phase: "intro",
  sessionId: null,
  secondsLeft: null,
  warned: false,
  turns: [],
  aids: [],
  hint: null,
  endReason: null,
  durationS: null,
  unavailable: null,
  lastError: null,
};

const LIVE: Phase[] = ["connecting", "listening", "coach_speaking", "ending"];

export function unavailableFor(code: string): Unavailable {
  switch (code) {
    case "capability_disabled":
      return "disabled";
    case "budget_exhausted":
      return "budget";
    case "voice_busy":
      return "busy";
    case "voice_session_exists":
      return "existing";
    default:
      return "error";
  }
}

export function reduce(state: CoachState, event: CoachEvent): CoachState {
  switch (event.type) {
    case "start":
      return state.phase === "intro" ? { ...initialState, phase: "connecting" } : state;
    case "session_created":
      return state.phase === "connecting" ? { ...state, sessionId: event.sessionId } : state;
    case "create_failed":
      return { ...state, phase: "unavailable", unavailable: unavailableFor(event.code) };
    case "mic_denied":
      return { ...state, phase: "unavailable", unavailable: "microphone" };
    case "ready":
      return state.phase === "connecting" ? { ...state, phase: "listening", secondsLeft: event.seconds } : state;
    case "agent_speaking":
      return state.phase === "listening" ? { ...state, phase: "coach_speaking" } : state;
    case "agent_done":
      return state.phase === "coach_speaking" ? { ...state, phase: "listening" } : state;
    case "user_started_speaking":
      // El alumno interrumpe: se vacía la reproducción y vuelve a escuchar.
      return state.phase === "coach_speaking" ? { ...state, phase: "listening" } : state;
    case "transcript":
      return LIVE.includes(state.phase) ? { ...state, turns: [...state.turns, event.turn] } : state;
    case "aid":
      return LIVE.includes(state.phase) ? { ...state, aids: [...state.aids, { kind: event.kind }] } : state;
    case "hint":
      return { ...state, hint: event.text };
    case "warning":
      return { ...state, warned: true, secondsLeft: event.secondsLeft };
    case "tick":
      return state.secondsLeft !== null && (state.phase === "listening" || state.phase === "coach_speaking")
        ? { ...state, secondsLeft: Math.max(0, state.secondsLeft - 1) }
        : state;
    case "stop":
      return LIVE.includes(state.phase) ? { ...state, phase: "ending" } : state;
    case "ended":
      return state.phase === "ended"
        ? state
        : { ...state, phase: "ended", endReason: event.reason, durationS: event.durationS, secondsLeft: 0 };
    case "socket_closed":
      // Sin `ended` del servidor: se perdió la conexión (no hay reconexión a media sesión).
      return LIVE.includes(state.phase)
        ? { ...state, phase: "ended", endReason: "connection_lost", secondsLeft: 0 }
        : state;
    case "server_error":
      return { ...state, lastError: event.code };
    case "reset":
      return initialState;
  }
}

export const PHASE_LABEL: Record<Phase, string> = {
  intro: "Antes de empezar",
  connecting: "Conectando",
  listening: "Te escucho",
  coach_speaking: "El coach está hablando",
  ending: "Terminando",
  ended: "Terminado",
  unavailable: "No disponible",
};

export const END_TEXT: Record<EndReason, string> = {
  deadline: "Se acabó el tiempo de la práctica.",
  user_stop: "Detuviste la práctica.",
  disconnect: "La conexión se cerró.",
  provider_error: "El servicio de voz falló. Puedes practicar este escenario por texto.",
  logout: "Tu sesión terminó en otra pestaña.",
  silence: "Terminamos porque no escuchamos nada en un rato.",
  expired: "La sesión expiró.",
  background: "La práctica terminó porque la pestaña pasó a segundo plano.",
  connection_lost: "Se perdió la conexión. No se puede retomar a media conversación.",
};
