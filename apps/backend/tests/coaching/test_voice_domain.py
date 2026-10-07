"""Reglas puras del coach de voz (REQ-05): tiempos, costo, límites por segundo, turnos con
ayuda y el mensaje `Settings` construido desde el escenario."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.modules.coaching.voice import domain
from app.modules.coaching.voice.settings_builder import AgentConfig, build_settings, prompt_for

T0 = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
SCENARIO = {
    "situation_en": "You go to the front desk of an adult language center.",
    "learner_role_en": "A working adult who wants to join an evening course.",
    "agent_persona_en": "A friendly receptionist at an adult language center.",
    "opening_en": "Good afternoon, Lakeside Language Center. How can I help you?",
    "required_moves": ["Ask about the price", "Close the conversation politely"],
    "coach_hints": ["Start by saying what you need."],
    "max_seconds": 300,
}


def test_deadlines_and_billable_seconds() -> None:
    assert domain.session_seconds(300, 300) == 300 and domain.session_seconds(300, 3) == 3
    deadline = domain.deadline_for(T0, 300)
    assert deadline == T0 + timedelta(seconds=330)  # máximo + gracia para conectar
    assert domain.connect_by(T0) == T0 + timedelta(seconds=30)
    # La conversación dura el máximo desde el inicio, pero nunca pasa del deadline.
    assert domain.conversation_end(T0 + timedelta(seconds=10), 300, deadline) == T0 + timedelta(
        seconds=310
    )
    assert domain.conversation_end(T0 + timedelta(seconds=40), 300, deadline) == deadline
    assert domain.billable_seconds(None, T0) == 0
    assert domain.billable_seconds(T0, T0 + timedelta(seconds=61, milliseconds=1)) == 62
    # USD 0.075/min: 300 s = 375 000 µUSD; 62 s = 77 500.
    assert domain.cost_microusd(300, 75_000) == 375_000
    assert domain.cost_microusd(62, 75_000) == 77_500


def test_rate_window_per_second() -> None:
    window = domain.RateWindow(limit=2)
    assert [window.allow(10.0), window.allow(10.1), window.allow(10.2)] == [True, True, False]
    assert window.allow(11.05)  # nueva ventana


def test_transcript_marks_the_repeat_aid_and_roles() -> None:
    transcript = domain.Transcript()
    transcript.add("assistant", "Good afternoon.", 0.0)
    transcript.pending_repeats = 1
    aid = transcript.add("user", domain.REPEAT_REQUEST, 3.24)
    spoken = transcript.add("user", "How much is it?", 5.0)
    assert [t["role"] for t in transcript.as_list()] == ["coach", "learner", "learner"]
    assert aid.aid and not spoken.aid and aid.at_s == 3.2 and spoken.n == 3
    assert domain.next_hint(["a", "b"], 1) == "b" and domain.next_hint(["a"], 1) is None


def test_settings_message_from_the_scenario() -> None:
    config = AgentConfig("nova-3", "open_ai", "gpt-4o-mini", "aura-2-thalia-en", 24_000)
    message = build_settings(SCENARIO, config)
    assert message["type"] == "Settings"
    assert message["audio"]["input"] == {"encoding": "linear16", "sample_rate": 16_000}
    assert message["audio"]["output"]["sample_rate"] == 24_000
    agent = message["agent"]
    assert agent["listen"]["provider"] == {"type": "deepgram", "model": "nova-3"}
    assert agent["think"]["provider"] == {"type": "open_ai", "model": "gpt-4o-mini"}
    assert agent["speak"]["provider"]["model"] == "aura-2-thalia-en"
    assert agent["greeting"] == SCENARIO["opening_en"]
    prompt = prompt_for(SCENARIO)
    for expected in (
        "friendly receptionist",
        "Ask about the price",
        "Stay inside this scenario",
        "B1 to B2 level",
        "two sentences at most",
        "Never ask for personal data",
        "Never give grades, scores, bands or levels",
        "switches to Spanish",
    ):
        assert expected in prompt
    assert "key" not in str(message).lower()  # ninguna llave en el mensaje


def test_rate_window_slides_instead_of_resetting() -> None:
    """A lo sumo `limit` eventos en cualquier segundo, también en el borde de la ventana."""
    window = domain.RateWindow(limit=50)
    allowed = sum(window.allow(1000.0 + i * 0.0001) for i in range(100))
    allowed += sum(window.allow(1000.999 + i * 0.00001) for i in range(100))
    assert allowed == 50
    assert window.allow(1001.0001)  # el primero ya salió de la ventana


def test_fake_agent_url_must_be_plain_localhost() -> None:
    from app.bootstrap import local_agent_url

    assert local_agent_url("ws://127.0.0.1:8765/v1/agent/converse")
    assert local_agent_url("ws://localhost:9/x")
    for bad in (
        None,
        "",
        "wss://agent.deepgram.com/v1/agent/converse",
        "ws://localhost:@evil.example:443/v1",
        "ws://user:pw@127.0.0.1:1/x",
        "ws://127.0.0.1.evil.example/x",
        "http://127.0.0.1:1/x",
    ):
        assert not local_agent_url(bad), bad


def test_a_pending_repeat_is_forgotten_when_the_next_learner_turn_differs() -> None:
    """Verificador ronda 2: sin eco de la ayuda (o con `InjectionRefused`), un «Could you
    repeat that?» dicho después por el alumno es suyo; dos «repetir» seguidos marcan sus dos
    ecos."""
    transcript = domain.Transcript()
    transcript.pending_repeats = 1
    own = transcript.add("user", "Sorry, how much is it?", 2.0)
    later = transcript.add("user", domain.REPEAT_REQUEST, 6.0)
    assert not own.aid and not later.aid and transcript.pending_repeats == 0
    transcript.pending_repeats = 2
    first = transcript.add("user", domain.REPEAT_REQUEST, 8.0)
    transcript.add("assistant", "Sure.", 9.0)
    second = transcript.add("user", domain.REPEAT_REQUEST, 10.0)
    assert first.aid and second.aid and transcript.pending_repeats == 0
