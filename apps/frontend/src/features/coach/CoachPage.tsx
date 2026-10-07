import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { api, newIdempotencyKey, unwrap } from "../../api/client";
import { ApiError } from "../../api/errors";
import { Button } from "../../components/Button";
import { Notice } from "../../components/Notice";
import { Page } from "../../components/Page";
import { useCapabilities } from "../feedback/capabilities";
import { LessonRating } from "../feedback/LessonRating";
import styles from "./CoachPage.module.css";
import { END_TEXT, type EndReason, PHASE_LABEL, type Turn, initialState, reduce } from "./machine";
import { useVoiceCapture } from "./useVoiceCapture";
import { usePcmPlayback } from "./usePcmPlayback";
import { type VoiceSession, VoiceFeedback } from "./VoiceFeedback";

const UNAVAILABLE_TEXT = {
  disabled: "La práctica por voz no está disponible ahora.",
  budget: "La práctica por voz no está disponible ahora.",
  busy: "Hay muchas prácticas de voz abiertas. Intenta en unos minutos.",
  existing: "Ya tienes una práctica de voz abierta en otra pestaña.",
  microphone: "No pudimos usar el micrófono. Puedes darle permiso en la configuración del sitio o practicar por texto.",
  provider: "El servicio de voz falló.",
  error: "No pudimos empezar la práctica por voz.",
} as const;

type ServerEvent =
  | { type: "ready"; seconds: number; sample_rate?: number | null }
  | { type: "transcript"; turn: Turn }
  | { type: "user_started_speaking" }
  | { type: "agent_speaking" }
  | { type: "agent_done" }
  | { type: "hint"; text: string | null }
  | { type: "warning"; seconds_left: number }
  | { type: "error"; code: string }
  | { type: "ended"; reason: EndReason; duration_s: number | null };

function wsUrl(path: string): string {
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${window.location.host}${path}`;
}

function clock(seconds: number | null): string {
  if (seconds === null) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

/** Coach de voz de un escenario (MVP-02 REQ-06). El servidor manda el tiempo y el corte; el
 * reloj de aquí solo informa. Sin voz, la alternativa es el mismo escenario por texto. */
export function CoachPage() {
  const { itemId = "" } = useParams();
  const scenario = useQuery({
    queryKey: ["scenario", itemId],
    queryFn: () => unwrap(api.GET("/api/v1/scenarios/{item_id}", { params: { path: { item_id: itemId } } })),
  });
  const capabilities = useCapabilities();
  const queryClient = useQueryClient();
  const [state, dispatch] = useReducer(reduce, initialState);
  const [save, setSave] = useState(false);
  const [captions, setCaptions] = useState(true);
  const socket = useRef<WebSocket | null>(null);
  const background = useRef(false);
  const playback = usePcmPlayback();

  const send = useCallback((frame: ArrayBuffer) => {
    if (socket.current?.readyState === WebSocket.OPEN) socket.current.send(frame);
  }, []);
  const capture = useVoiceCapture(send);

  const teardown = useCallback(() => {
    capture.stop();
    playback.close();
    const ws = socket.current;
    socket.current = null;
    if (ws && ws.readyState <= WebSocket.OPEN) ws.close(1000);
  }, [capture, playback]);

  // Al salir de la página se corta todo (solo al desmontar, no en cada render).
  const teardownRef = useRef(teardown);
  useEffect(() => {
    teardownRef.current = teardown;
  }, [teardown]);
  useEffect(() => () => teardownRef.current(), []);

  const control = (message: Record<string, string>) => {
    if (socket.current?.readyState === WebSocket.OPEN) socket.current.send(JSON.stringify(message));
  };

  const onServer = useCallback(
    (event: ServerEvent) => {
      switch (event.type) {
        case "ready":
          playback.setRate(event.sample_rate);
          dispatch({ type: "ready", seconds: event.seconds });
          break;
        case "transcript":
          dispatch({ type: "transcript", turn: event.turn });
          break;
        case "user_started_speaking":
          playback.flush(); // el alumno interrumpe al coach
          dispatch({ type: "user_started_speaking" });
          break;
        case "agent_speaking":
        case "agent_done":
          dispatch({ type: event.type });
          break;
        case "hint":
          dispatch({ type: "hint", text: event.text });
          break;
        case "warning":
          dispatch({ type: "warning", secondsLeft: event.seconds_left });
          break;
        case "error":
          dispatch({ type: "server_error", code: event.code });
          break;
        case "ended":
          dispatch({
            type: "ended",
            reason: background.current ? "background" : event.reason,
            durationS: event.duration_s,
          });
          playback.finish(2); // el coach acaba su frase, 2 s como máximo (EDGE-13)
          teardown();
          break;
      }
    },
    [playback, teardown],
  );

  const begin = async () => {
    dispatch({ type: "start" });
    background.current = false;
    await playback.prime(); // el gesto de "Empezar" desbloquea el audio (Safari iOS)
    const micError = await capture.start(); // permiso negado, sin micrófono o sin soporte
    if (micError) {
      playback.close();
      dispatch({ type: "mic_denied" });
      return;
    }
    let session: { id: string; ws_path: string };
    try {
      session = await unwrap(
        api.POST("/api/v1/voice-sessions", {
          params: { header: { "Idempotency-Key": newIdempotencyKey() } },
          body: { scenario_id: itemId, accept_voice_notice: true, save_transcript: save },
        }),
      );
    } catch (err) {
      teardown();
      dispatch({ type: "create_failed", code: err instanceof ApiError ? err.code : "error" });
      return;
    }
    dispatch({ type: "session_created", sessionId: session.id });
    const ws = new WebSocket(wsUrl(session.ws_path));
    ws.binaryType = "arraybuffer";
    socket.current = ws;
    ws.onmessage = (e: MessageEvent<ArrayBuffer | string>) => {
      if (typeof e.data === "string") onServer(JSON.parse(e.data) as ServerEvent);
      else playback.enqueue(e.data);
    };
    ws.onclose = () => {
      dispatch({ type: "socket_closed" });
      teardown();
    };
  };

  const live = ["connecting", "listening", "coach_speaking", "ending"].includes(state.phase);

  // Reloj informativo y fin al pasar a segundo plano (Safari iOS corta el audio).
  useEffect(() => {
    if (!live) return;
    const timer = window.setInterval(() => dispatch({ type: "tick" }), 1000);
    const onVisibility = () => {
      if (document.visibilityState === "hidden") {
        background.current = true;
        control({ type: "stop" });
        dispatch({ type: "stop" });
      }
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [live]);

  const summary = useQuery({
    queryKey: ["voice-session", state.sessionId],
    enabled: state.phase === "ended" && state.sessionId !== null,
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/voice-sessions/{session_id}", {
          params: { path: { session_id: state.sessionId ?? "" } },
        }),
      ),
  });

  const data = scenario.data;
  const textMode = (
    <Link to={`/escenarios/${itemId}`} className={styles.textMode}>
      Practicar este escenario por texto
    </Link>
  );

  if (scenario.isPending) return <Page title="Coach de voz">Cargando…</Page>;
  if (!data) {
    return (
      <Page title="Coach de voz">
        <Notice tone="system-error">No encontramos este escenario.</Notice>
        <Link to="/ruta">Ir a la ruta</Link>
      </Page>
    );
  }
  const voiceOff = capabilities.data?.voice === false;
  const minutes = Math.round((data.max_seconds ?? 300) / 60);

  return (
    <Page title={`${data.title} · voz`} heading={data.title} wide>
      <p className={styles.mode}>Práctica por voz con el coach. No es una tarea del examen oficial.</p>

      {state.phase === "intro" ? (
        <section aria-label="Antes de empezar" className={styles.intro}>
          {data.situation_es ? <p>{data.situation_es}</p> : null}
          {data.objective_es ? (
            <p>
              <strong>Objetivo:</strong> {data.objective_es}
            </p>
          ) : null}
          {data.required_moves?.length ? (
            <>
              <p>Lo que tienes que lograr:</p>
              <ul lang="en">
                {data.required_moves.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            </>
          ) : null}
          <p>
            <strong>Duración:</strong> hasta {minutes} minutos. Hablas con el coach en inglés; puedes pedir que
            repita, que hable más despacio o una pista, y detener cuando quieras.
          </p>
          <p>Te recomendamos usar audífonos para que el coach no se escuche a sí mismo.</p>
          <Notice tone="info" title="Aviso de procesamiento de voz">
            Tu voz se envía a Deepgram, un servicio de reconocimiento y síntesis de voz, para que el coach te entienda y
            te responda. No guardamos el audio. Más detalles en el{" "}
            <Link to="/privacidad">aviso de privacidad</Link>.
          </Notice>
          <label className={styles.consent}>
            <input type="checkbox" checked={save} onChange={(e) => setSave(e.target.checked)} />
            Guardar la transcripción y el feedback en mi progreso
          </label>
          {voiceOff ? (
            <Notice tone="note" title={UNAVAILABLE_TEXT.disabled}>
              {textMode}
            </Notice>
          ) : (
            <div className={styles.actions}>
              <Button onClick={() => void begin()}>Empezar</Button>
              {textMode}
            </div>
          )}
        </section>
      ) : null}

      {live ? (
        <section aria-label="Conversación" className={styles.live}>
          <p className={styles.phase} role="status" aria-live="polite">
            <span className={styles[state.phase]} aria-hidden="true" /> {PHASE_LABEL[state.phase]}
          </p>
          <p className={styles.time}>
            Tiempo restante: <strong>{clock(state.secondsLeft)}</strong>
            {state.warned ? <span className={styles.warning}> · quedan menos de 30 segundos</span> : null}
          </p>
          <div className={styles.aids} role="group" aria-label="Ayudas">
            <Button
              variant="secondary"
              disabled={state.phase === "connecting"}
              onClick={() => {
                control({ type: "aid", kind: "repeat" });
                dispatch({ type: "aid", kind: "repeat" });
              }}
            >
              Repetir
            </Button>
            <Button
              variant="secondary"
              disabled={state.phase === "connecting"}
              onClick={() => {
                control({ type: "aid", kind: "slower" });
                dispatch({ type: "aid", kind: "slower" });
              }}
            >
              Más despacio
            </Button>
            <Button
              variant="secondary"
              disabled={state.phase === "connecting"}
              onClick={() => {
                control({ type: "aid", kind: "hint" });
                dispatch({ type: "aid", kind: "hint" });
              }}
            >
              Pista
            </Button>
            <Button
              variant="quiet"
              disabled={state.phase === "ending"}
              onClick={() => {
                control({ type: "stop" });
                dispatch({ type: "stop" });
              }}
            >
              Detener
            </Button>
          </div>
          {state.hint ? (
            <Notice tone="note" title="Pista">
              <span lang="en">{state.hint}</span>
            </Notice>
          ) : null}
          {state.lastError === "rate_limited" ? <p>Espera un momento antes de pedir otra ayuda.</p> : null}
          {state.lastError === "aid_refused" ? (
            <p>El coach no pudo repetir en este momento. Intenta de nuevo cuando termine de hablar.</p>
          ) : null}
          <label className={styles.consent}>
            <input type="checkbox" checked={captions} onChange={(e) => setCaptions(e.target.checked)} />
            Subtítulos en vivo
          </label>
          {captions ? (
            <ol className={styles.turns} aria-live="polite" aria-label="Subtítulos">
              {state.turns.map((t) => (
                <li key={t.n} className={t.role === "coach" ? styles.coach : styles.learner}>
                  <span className={styles.who}>{t.role === "coach" ? "Coach" : "Tú"}</span>{" "}
                  <span lang="en">{t.text}</span>
                  {t.aid ? <span className={styles.aid}> (ayuda)</span> : null}
                </li>
              ))}
            </ol>
          ) : null}
        </section>
      ) : null}

      {state.phase === "ended" ? (
        <section aria-label="Resumen" className={styles.summary}>
          <Notice tone={state.endReason === "provider_error" ? "note" : "info"} title="Terminó la práctica">
            {state.endReason ? END_TEXT[state.endReason] : null}
          </Notice>
          <p>
            <strong>Duración:</strong> {clock(summary.data?.duration_s ?? state.durationS ?? 0)} ·{" "}
            <strong>Ayudas:</strong> {summary.data?.aids.length ?? state.aids.length}
          </p>
          {summary.data ? (
            <VoiceFeedback
              session={summary.data}
              onSession={(s: VoiceSession) => queryClient.setQueryData(["voice-session", state.sessionId], s)}
            />
          ) : null}
          <div className={styles.actions}>
            <Button onClick={() => dispatch({ type: "reset" })}>Intentar de nuevo</Button>
            {textMode}
          </div>
          {state.sessionId && summary.data?.started_at ? (
            <LessonRating itemId={state.sessionId} noun="esta práctica de voz" contextType="voice" />
          ) : null}
        </section>
      ) : null}

      {state.phase === "unavailable" ? (
        <Notice tone="note" title={state.unavailable ? UNAVAILABLE_TEXT[state.unavailable] : null}>
          <p>{textMode}</p>
          {state.unavailable === "busy" || state.unavailable === "error" ? (
            <Button variant="secondary" onClick={() => dispatch({ type: "reset" })}>
              Volver
            </Button>
          ) : null}
        </Notice>
      ) : null}
    </Page>
  );
}
