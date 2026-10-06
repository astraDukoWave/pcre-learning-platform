"""Resumen por objetivo de una corrida (REQ-12): sin respuesta cuenta en el total, el audio
que no cargó queda aparte y las producciones no se califican solas."""

from __future__ import annotations

from app.modules.practice import domain

OK = domain.Grade("evaluated", "auto", 1.0, True)
WRONG = domain.Grade("evaluated", "auto", 0.0, False)
PENDING = domain.Grade("pending", "self", None, None)
NO_RECORDING = domain.Grade("not_evaluable", "self", None, None)


def test_summary_by_objective() -> None:
    summary = domain.assessment_summary(
        [
            domain.ScoredItem(("U1.R",), "choice", OK),
            domain.ScoredItem(("U1.R", "U2.R"), "word_completion", WRONG),
            domain.ScoredItem(("U2.R",), "sentence_order", None),  # sin responder
            domain.ScoredItem(("U1.L",), "choice", domain.audio_not_evaluable({}), True),
            domain.ScoredItem(("U1.W",), "short_writing", PENDING),
            domain.ScoredItem(("U1.S",), "recorded_speaking", NO_RECORDING),
        ]
    )
    assert summary == {
        "objectives": [
            {"code": "U1.L", "correct": 0, "total": 0, "not_evaluable": 1},
            {"code": "U1.R", "correct": 1, "total": 2, "not_evaluable": 0},
            {"code": "U2.R", "correct": 0, "total": 2, "not_evaluable": 0},
        ],
        "closed_correct": 1,
        "closed_total": 3,
        "productions_answered": 1,
        "productions_total": 2,
        "not_evaluable_audio": 1,
    }
    assert domain.audio_not_evaluable({"selected": ["a"]}).result["reason"] == "audio"
