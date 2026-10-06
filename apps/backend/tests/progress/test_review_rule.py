"""AC-12 (dominio): repaso 1/3/7 con reinicio y ayudas que no avanzan, con reloj falso."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.modules.progress.domain import ReviewState, next_review_state

NOW = datetime(2026, 10, 5, 15, 0, tzinfo=UTC)
INTERVALS = (24, 72, 168)


def step(current: ReviewState | None, **kw: object) -> ReviewState | None:
    args = {"aided": False, "mode": "review", "first_attempt": False, "intervals_hours": INTERVALS}
    args.update(kw)
    return next_review_state(current, **args)  # type: ignore[arg-type]


def test_first_practice_failure_schedules_review_in_24h() -> None:
    state = step(None, outcome="incorrect", mode="practice", first_attempt=True, now=NOW)
    assert state == ReviewState(0, NOW + timedelta(hours=24), "incorrect")


def test_practice_success_or_retry_does_not_schedule() -> None:
    assert step(None, outcome="correct", mode="practice", first_attempt=True, now=NOW) is None
    assert step(None, outcome="incorrect", mode="practice", first_attempt=False, now=NOW) is None


def test_unaided_successes_walk_1_3_7_then_stay_at_7() -> None:
    state = ReviewState(0, NOW + timedelta(hours=24), "incorrect")
    t = NOW + timedelta(hours=24)
    expected = [(1, 72), (2, 168), (3, 168), (3, 168)]
    for stage, hours in expected:
        nxt = step(state, outcome="correct", now=t)
        assert nxt is not None
        assert (nxt.stage, nxt.due_at - t) == (stage, timedelta(hours=hours))
        state, t = nxt, nxt.due_at


def test_failure_resets_and_aided_success_does_not_advance() -> None:
    state = ReviewState(2, NOW, "correct")
    reset = step(state, outcome="incorrect", now=NOW)
    assert reset == ReviewState(0, NOW + timedelta(hours=24), "incorrect")
    aided = step(state, outcome="correct", aided=True, now=NOW)
    assert aided is not None and aided.stage == 2 and aided.last_outcome == "correct_aided"


def test_early_review_does_not_advance() -> None:
    state = ReviewState(1, NOW + timedelta(hours=10), "correct")
    assert step(state, outcome="correct", now=NOW) is None
