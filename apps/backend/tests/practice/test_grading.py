"""AC-10 (dominio): corrección determinista por formato con variantes válidas."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.modules.practice import domain

CHOICE_PUBLIC = {
    "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}, {"id": "c", "text": "C"}],
    "multiple": False,
}
CHOICE_SOLUTION = {"correct": ["a"], "why": {"b": "B es en sábado."}}


def test_choice_correct_and_incorrect_with_option_feedback() -> None:
    ok = domain.grade("choice", {"selected": ["a"]}, CHOICE_PUBLIC, CHOICE_SOLUTION, None)
    assert ok.correct is True and ok.score == 1.0
    bad = domain.grade("choice", {"selected": ["b"]}, CHOICE_PUBLIC, CHOICE_SOLUTION, None)
    assert bad.correct is False
    assert bad.result["option_feedback"] == {"b": "B es en sábado."}
    assert bad.result["correct_options"] == ["a"]


def test_multiple_choice_requires_the_exact_set() -> None:
    public = {**CHOICE_PUBLIC, "multiple": True}
    solution = {"correct": ["a", "c"]}
    assert domain.grade("choice", {"selected": ["c", "a"]}, public, solution, None).correct is True
    assert domain.grade("choice", {"selected": ["a"]}, public, solution, None).correct is False


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"selected": []},
        {"selected": ["z"]},
        {"selected": ["a", "b"]},
        {"selected": "a"},
        {"selected": ["a", "a"]},
    ],
)
def test_choice_rejects_invalid_shapes(response: dict[str, object]) -> None:
    with pytest.raises(domain.InvalidResponse):
        domain.grade("choice", response, CHOICE_PUBLIC, CHOICE_SOLUTION, None)


WC_PUBLIC = {
    "text_en": "I {{g1}} to work and I am {{g2}}.",
    "gaps": [{"id": "g1", "shown": "tra"}, {"id": "g2", "shown": "ti"}],
}
WC_SOLUTION = {
    "gaps": [
        {"id": "g1", "accepted": ["travel"], "case_sensitive": False},
        {"id": "g2", "accepted": ["tired", "tiring"], "case_sensitive": False},
    ]
}


@pytest.mark.parametrize(
    ("answers", "per_gap"),
    [
        ({"g1": "travel", "g2": "tired"}, {"g1": True, "g2": True}),
        ({"g1": "vel", "g2": "red"}, {"g1": True, "g2": True}),  # solo lo que falta
        ({"g1": "TRAVEL ", "g2": "Tiring"}, {"g1": True, "g2": True}),  # mayúsculas y espacios
        ({"g1": "travels", "g2": "tire"}, {"g1": False, "g2": False}),
    ],
)
def test_word_completion_accepts_variants(
    answers: dict[str, str], per_gap: dict[str, bool]
) -> None:
    graded = domain.grade("word_completion", {"answers": answers}, WC_PUBLIC, WC_SOLUTION, None)
    assert graded.result["per_gap"] == per_gap


def test_word_completion_case_sensitive_gap() -> None:
    solution = {
        "gaps": [
            {"id": "g1", "accepted": ["Travel"], "case_sensitive": True},
            WC_SOLUTION["gaps"][1],
        ]
    }
    graded = domain.grade(
        "word_completion", {"answers": {"g1": "travel", "g2": "tired"}}, WC_PUBLIC, solution, None
    )
    assert graded.result["per_gap"]["g1"] is False


def test_sentence_order_accepts_any_listed_order() -> None:
    public = {"tokens": ["usually", "I", "walk", "to work"]}
    solution = {
        "accepted_orders": [
            ["I", "usually", "walk", "to work"],
            ["usually", "I", "walk", "to work"],
        ]
    }
    for order in solution["accepted_orders"]:
        assert (
            domain.grade("sentence_order", {"order": order}, public, solution, None).correct is True
        )
    wrong = domain.grade(
        "sentence_order", {"order": ["walk", "I", "usually", "to work"]}, public, solution, None
    )
    assert (
        wrong.correct is False and wrong.result["correct_order"] == solution["accepted_orders"][0]
    )
    with pytest.raises(domain.InvalidResponse):
        domain.grade("sentence_order", {"order": ["I", "walk"]}, public, solution, None)


DIALOGUE_PUBLIC = {
    "start": "n1",
    "nodes": [
        {
            "id": "n1",
            "speaker": "agent",
            "text_en": "Hi",
            "options": [
                {"id": "a", "text": "x", "next": "n2"},
                {"id": "b", "text": "y", "next": "n2"},
            ],
        },
        {
            "id": "n2",
            "speaker": "agent",
            "text_en": "And?",
            "options": [{"id": "a", "text": "z", "next": "n3"}],
        },
        {"id": "n3", "speaker": "agent", "text_en": "Bye", "options": []},
    ],
}
DIALOGUE_SOLUTION = {
    "options": {
        "n1.a": {"feedback_es": "Bien", "good": True},
        "n1.b": {"feedback_es": "Breve", "good": False},
        "n2.a": {"feedback_es": "Ok", "good": True},
    },
    "success_paths": [["n1.a", "n2.a"]],
}


def test_guided_dialogue_follows_the_graph() -> None:
    good = domain.grade(
        "guided_dialogue", {"path": ["n1.a", "n2.a"]}, DIALOGUE_PUBLIC, DIALOGUE_SOLUTION, None
    )
    assert good.correct is True and good.score == 1.0
    other = domain.grade(
        "guided_dialogue", {"path": ["n1.b", "n2.a"]}, DIALOGUE_PUBLIC, DIALOGUE_SOLUTION, None
    )
    assert other.correct is False and other.result["turns"][0]["feedback_es"] == "Breve"
    for path in (["n2.a"], ["n1.a"], ["n1.z", "n2.a"]):
        with pytest.raises(domain.InvalidResponse):
            domain.grade(
                "guided_dialogue", {"path": path}, DIALOGUE_PUBLIC, DIALOGUE_SOLUTION, None
            )


RUBRIC = {"criteria": [{"id": "task"}, {"id": "organization"}]}


def test_short_writing_self_assessment() -> None:
    public = {"min_words": 3, "max_words": 10}
    pending = domain.grade(
        "short_writing", {"text": "Dear Ana, I would like info."}, public, {}, RUBRIC
    )
    assert pending.evaluation_status == "pending" and pending.evaluation_source == "self"
    scored = domain.grade(
        "short_writing",
        {"text": "Dear Ana, hi.", "self_assessment": {"task": 3, "organization": 0}},
        public,
        {},
        RUBRIC,
    )
    assert scored.evaluation_status == "evaluated" and scored.score == 0.5
    with pytest.raises(domain.InvalidResponse):
        domain.grade(
            "short_writing", {"text": "x", "self_assessment": {"task": 4}}, public, {}, RUBRIC
        )
    with pytest.raises(domain.InvalidResponse):
        domain.grade("short_writing", {"text": "a" * 4001}, public, {}, RUBRIC)


def test_recorded_speaking_could_not_record_is_not_evaluable() -> None:
    graded = domain.grade("recorded_speaking", {"recorded": False}, {}, {}, RUBRIC)
    assert graded.evaluation_status == "not_evaluable"


def test_request_hash_and_local_day() -> None:
    assert domain.request_hash({"a": 1, "b": [1]}) == domain.request_hash({"b": [1], "a": 1})
    late = datetime(2026, 10, 6, 4, 30, tzinfo=UTC)  # 23:30 del 5 en Ciudad de México
    assert domain.local_day(late, "America/Mexico_City") == date(2026, 10, 5)
    assert domain.local_day(late, "Europe/Madrid") == date(2026, 10, 6)
    assert domain.lesson_completed({"a", "b"}, {"a", "b", "c"})
    assert not domain.lesson_completed({"a", "b"}, {"a"})
