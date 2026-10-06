"""AC-03: el validador maneja salida rota, evidencia inventada, URLs, puntajes y campos de
más; la evidencia se compara literal sobre el texto normalizado (REQ-02)."""

from __future__ import annotations

import json
from typing import Any

from app.modules.coaching.feedback import domain

TEXT = (
    "Dear Northside, I am writing to ask about your evening classes. Could you tell me which "
    "days do the classes meet? I’d like to know the price per month.  Thank you, Ana"
)
CRITERIA = frozenset({"task", "organization", "language_control", "register"})


def obs(evidence: str, criterion: str = "language_control", **extra: str) -> dict[str, str]:
    return {
        "criterion": criterion,
        "evidence": evidence,
        "observation_es": "Después de «Could you tell me» va orden de afirmación.",
        "suggestion_es": "Escribe «which days the classes meet».",
        **extra,
    }


def check(raw: Any, max_observations: int = 3) -> domain.ValidatedFeedback:
    return domain.validate(
        raw, learner_text=TEXT, criteria=CRITERIA, max_observations=max_observations
    )


def test_literal_evidence_is_kept_with_normalized_spacing_quotes_and_case() -> None:
    out = check(
        {
            "status": "evaluable",
            "reason": None,
            "observations": [
                obs("which  days do the classes meet"),  # espacios distintos
                obs("I'd like to know the price", criterion="task"),  # comilla recta vs curva
                obs("THANK YOU, ANA", criterion="register"),  # mayúsculas
            ],
            "rubric_levels": {"task": 2, "register": 3, "language_control": 7, "nope": 1},
        }
    )
    assert out.status == "evaluable" and len(out.observations) == 3
    assert out.rubric_levels == {"task": 2, "register": 3}  # fuera de rango o criterio: fuera
    assert out.returned_observations == 3 and out.discarded == ()


def test_broken_or_non_object_output_is_not_evaluable() -> None:
    for raw in ('```json\n{"status": "evaluable"', "[1, 2]", "", None, "null"):
        out = check(raw)
        assert out.status == "not_evaluable" and out.reason == "invalid_output", raw


def test_invented_evidence_is_discarded_and_none_left_means_not_evaluable() -> None:
    out = check({"status": "evaluable", "observations": [obs("I has went to the classes")]})
    assert out.status == "not_evaluable" and out.reason == "no_valid_evidence"
    assert out.discarded == ("evidence_not_found",) and out.returned_observations == 1


def test_urls_exam_scores_extra_fields_and_unknown_criteria_are_discarded() -> None:
    out = check(
        {
            "status": "evaluable",
            "observations": [
                obs("which days do the classes meet", suggestion_es="Ver https://example.com"),
                obs("Thank you, Ana", criterion="register", observation_es="Tu score of 6/6."),
                obs("evening classes", criterion="task", confidence="0.9"),
                obs("the price per month", criterion="pronunciation"),
                obs("Dear Northside", criterion="organization"),
            ],
        }
    )
    assert [o.evidence for o in out.observations] == ["Dear Northside"]
    assert out.discarded == ("url", "exam_score", "shape", "unknown_criterion")


def test_evidence_may_quote_a_link_the_learner_wrote() -> None:
    text = "I found your ad on https://example.com/classes and I want to join."
    quoted = {
        "status": "evaluable",
        "observations": [obs("I found your ad on https://example.com/classes", criterion="task")],
    }
    out = domain.validate(quoted, learner_text=text, criteria=CRITERIA, max_observations=3)
    assert out.status == "evaluable" and out.discarded == ()


def test_extra_top_level_field_invalidates_the_whole_output() -> None:
    raw = json.dumps({"status": "evaluable", "observations": [obs("evening classes")], "score": 6})
    assert check(raw).reason == "invalid_output"


def test_limit_of_observations_and_abstention_reasons() -> None:
    many = {"status": "evaluable", "observations": [obs("Dear Northside", "organization")] * 4}
    out = check(many, max_observations=2)
    assert len(out.observations) == 2 and out.discarded == ("over_limit", "over_limit")
    assert check({"status": "not_evaluable", "reason": "other_language"}).reason == "other_language"
    assert check({"status": "not_evaluable", "reason": "made_up"}).reason == "invalid_output"
    assert check({"status": "great"}).reason == "invalid_output"


def test_disputed_turns_hide_their_observations() -> None:
    turns = ["Hi, how much is it per month?", "I want the Monday group"]
    kept = (
        domain.Observation("required_moves", "how much is it", "a", "b"),
        domain.Observation("language_control", "I want the Monday group", "a", "b"),
        domain.Observation("language_control", "per month? | I want the Monday", "a", "b"),
    )
    visible = domain.visible_after_disputes(kept, turns, {0})
    assert [o.evidence for o in visible] == ["I want the Monday group"]
    # La evidencia que cruza turnos no está completa en ninguno: se oculta.
    assert [o.evidence for o in domain.visible_after_disputes(kept, turns, {1})] == [
        "how much is it"
    ]
    assert len(domain.visible_after_disputes(kept, turns, set())) == 2


def test_links_without_scheme_and_emails_are_discarded() -> None:
    for text in (
        "Repasa en bbc.co.uk/learningenglish/grammar",
        "Más ejemplos en grammarly.com/blog/indirect-questions",
        "Ver youtu.be/abc123",
        "Lee [la guía](bit.ly/x1)",
        "Repasa más en example.com",
        "Escribe a ayuda@example.com",
    ):
        out = check(
            {"status": "evaluable", "observations": [obs("Dear Northside", suggestion_es=text)]}
        )
        assert out.discarded == ("url",), text
    for text in (
        "Usa «which days», p. ej. «Which days do the classes meet?»",
        "Agrega un dato, etc.",
    ):
        assert domain.forbidden_content(text) is None, text


def test_scores_bands_grades_and_levels_in_spanish_are_discarded() -> None:
    for text in (
        "Tu respuesta merece 5 de 6.",
        "Mereces 6/6.",
        "Sacarías 30 sobre 30.",
        "Una puntuación de 25.",
        "Tu calificación sería 4/5.",
        "Banda 7 de IELTS.",
        "Score: 28 en Writing.",
        "Tu nivel es C2.",
        "Ya estás en B2.",
    ):
        out = check(
            {"status": "evaluable", "observations": [obs("Dear Northside", observation_es=text)]}
        )
        assert out.discarded == ("exam_score",), text
    assert domain.forbidden_content("Tu correo pide 2 de los 3 datos.") is None


def test_evidence_must_be_whole_words_and_survives_the_prompt_delimiter() -> None:
    assert not domain.evidence_in("ch da", TEXT) and not domain.evidence_in("lasses", TEXT)
    assert domain.evidence_in("which days", TEXT) and not domain.evidence_in("...", TEXT)
    # El prompt cambia < > por ‹ › (prompts.delimit) y el modelo cita lo que vio.
    assert domain.evidence_in("I ‹3 this course", "Hi! I <3 this course.")
    # Ancho completo y ligaduras se comparan en NFKC.
    assert domain.evidence_in("ＷＨＩＣＨ days", TEXT)
