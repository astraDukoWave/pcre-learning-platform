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
    kept = (
        domain.Observation("required_moves", "how much is it", "a", "b"),
        domain.Observation("language_control", "I want the Monday group", "a", "b"),
    )
    visible = domain.hidden_by_disputes(kept, ["Hi, how much is it per month?"])
    assert [o.evidence for o in visible] == ["I want the Monday group"]
