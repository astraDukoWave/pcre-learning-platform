import { describe, expect, it } from "vitest";
import { type CoachState, initialState, reduce } from "./machine";

function run(...events: Parameters<typeof reduce>[1][]): CoachState {
  return events.reduce(reduce, initialState);
}

const turn = (n: number, role: "coach" | "learner", aid = false) => ({ n, role, text: `t${n}`, at_s: n, aid });

describe("coach state machine", () => {
  it("goes through a whole conversation", () => {
    let s = run({ type: "start" }, { type: "session_created", sessionId: "s1" });
    expect([s.phase, s.sessionId]).toEqual(["connecting", "s1"]);
    s = reduce(s, { type: "ready", seconds: 300 });
    expect([s.phase, s.secondsLeft]).toEqual(["listening", 300]);
    s = reduce(s, { type: "agent_speaking" });
    expect(s.phase).toBe("coach_speaking");
    s = reduce(s, { type: "user_started_speaking" }); // interrumpe al coach
    expect(s.phase).toBe("listening");
    s = reduce(reduce(s, { type: "transcript", turn: turn(1, "coach") }), { type: "transcript", turn: turn(2, "learner") });
    s = reduce(s, { type: "aid", kind: "repeat" });
    s = reduce(s, { type: "hint", text: "Ask about the price." });
    s = reduce(reduce(s, { type: "tick" }), { type: "warning", secondsLeft: 30 });
    expect([s.turns.length, s.aids.length, s.hint, s.warned, s.secondsLeft]).toEqual([2, 1, "Ask about the price.", true, 30]);
    s = reduce(s, { type: "stop" });
    expect(s.phase).toBe("ending");
    s = reduce(s, { type: "ended", reason: "user_stop", durationS: 42 });
    expect([s.phase, s.endReason, s.durationS]).toEqual(["ended", "user_stop", 42]);
    expect(reduce(s, { type: "socket_closed" })).toBe(s); // el cierre posterior no cambia nada
  });

  it("falls back to text when voice is not available", () => {
    expect(run({ type: "start" }, { type: "create_failed", code: "capability_disabled" }).unavailable).toBe("disabled");
    expect(run({ type: "start" }, { type: "create_failed", code: "budget_exhausted" }).unavailable).toBe("budget");
    expect(run({ type: "start" }, { type: "create_failed", code: "voice_busy" }).unavailable).toBe("busy");
    expect(run({ type: "start" }, { type: "mic_denied" }).phase).toBe("unavailable");
  });

  it("treats a lost socket as the end, without reconnecting", () => {
    const s = run({ type: "start" }, { type: "ready", seconds: 300 }, { type: "socket_closed" });
    expect([s.phase, s.endReason]).toEqual(["ended", "connection_lost"]);
  });

  it("ignores events that do not apply to the current phase", () => {
    expect(run({ type: "ready", seconds: 10 }).phase).toBe("intro");
    expect(run({ type: "transcript", turn: turn(1, "coach") }).turns).toEqual([]);
    expect(run({ type: "tick" }).secondsLeft).toBeNull();
    const ended = run({ type: "start" }, { type: "ready", seconds: 1 }, { type: "ended", reason: "deadline", durationS: 1 });
    expect(reduce(ended, { type: "ended", reason: "silence", durationS: 5 }).endReason).toBe("deadline");
    expect(reduce(ended, { type: "reset" }).phase).toBe("intro");
  });
});
