"""REQ-07: cada regla del lint, con la ruta de prueba válida como base."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from app.modules.content.lint import lint_dir
from app.modules.content.loader import Issue
from tests.content.builder import add_listening, write_content

Mutation = Callable[[dict[str, Any]], None]


def _issues(tmp_path: Path, mutate: Mutation | None = None) -> list[Issue]:
    root = write_content(tmp_path, mutate)
    ((_, issues),) = lint_dir(root).values()
    return issues


def _codes(issues: list[Issue], severity: str) -> set[str]:
    return {i.code for i in issues if i.severity == severity}


def test_valid_fixture_has_no_errors(tmp_path: Path) -> None:
    issues = _issues(tmp_path)
    assert _codes(issues, "error") == set(), [i.render() for i in issues]


def _lesson(files: dict[str, Any]) -> dict[str, Any]:
    lesson: dict[str, Any] = files["units/u1/l1-lectura.yaml"]
    return lesson


ERROR_CASES: dict[str, tuple[Mutation, str]] = {
    "schema_extra_field": (lambda f: _lesson(f).update(color="rojo"), "schema"),
    "duplicate_key": (
        lambda f: f["units/u1/l3-escritura.yaml"]["activities"][0].update(key="u1.l1.p1"),
        "duplicate_key",
    ),
    "unknown_objective": (
        lambda f: _lesson(f)["activities"][0].update(objectives=["U9.R"]),
        "unknown_objective",
    ),
    "unknown_source": (
        lambda f: _lesson(f)["sources"].append({"source": "nada", "claim": "x", "scope": "y"}),
        "unknown_source",
    ),
    "unknown_rubric": (
        lambda f: f["units/u1/l3-escritura.yaml"]["activities"][0].update(rubric="nope"),
        "unknown_rubric",
    ),
    "unknown_unit": (lambda f: _lesson(f).update(unit="u9-nada"), "unknown_unit"),
    "minimum_items": (lambda f: _lesson(f)["activities"].pop(), "minimum_items"),
    "forbidden_marker": (
        lambda f: _lesson(f).update(title="Elegir un curso TODO"),
        "forbidden_marker",
    ),
    "support_in_review": (
        lambda f: _lesson(f)["activities"][5].update(support_es="Ayuda en español."),
        "support_es_not_allowed",
    ),
    "support_after_u4": (
        lambda f: _lesson(f).update(unit="u5-ideas-academicas"),
        "support_es_not_allowed",
    ),
    "aids_in_assessment": (
        lambda f: f["units/u1/checkpoint.yaml"]["activities"][0].update(hints=["pista"]),
        "aids_in_assessment",
    ),
    "assessment_pool_in_lesson": (
        lambda f: _lesson(f)["activities"][0].update(pool="assessment"),
        "pool_mismatch",
    ),
    "practice_pool_in_form": (
        lambda f: f["units/u1/checkpoint.yaml"]["activities"][0].update(pool="practice"),
        "pool_mismatch",
    ),
    "pool_overlap": (
        lambda f: (
            f["units/u1/checkpoint.yaml"]["activities"][0].update(
                prompt_en=_lesson(f)["activities"][0]["prompt_en"],
                options=_lesson(f)["activities"][0]["options"],
                stimulus={"text_en": f["units/u1/l1-lectura.yaml"]["passages"][0]["text_en"]},
            )
            or _lesson(f)["activities"][0].update(
                stimulus={"text_en": _lesson(f)["passages"][0]["text_en"]}
            )
        ),
        "pool_overlap",
    ),
    "family_format": (
        lambda f: _lesson(f)["activities"][0].update(task_family="write_an_email"),
        "family_format",
    ),
    "listening_without_audio": (
        lambda f: _lesson(f)["activities"][0].update(task_family="listen_announcement"),
        "listening_without_audio",
    ),
    "ets_required": (lambda f: _lesson(f).update(sources=[]), "ets_source_required"),
    "unknown_passage": (
        lambda f: _lesson(f)["activities"][0].update(stimulus={"passage": "p9"}),
        "unknown_passage",
    ),
    "checkpoint_minimum": (
        lambda f: f["units/u1/checkpoint.yaml"]["activities"].pop(0),
        "minimum_items",
    ),
    "audio_reference_missing": (
        lambda f: _lesson(f)["activities"][0].update(
            stimulus={"audio": "no-existe", "transcript": "x"}
        ),
        "unknown_audio",
    ),
}


@pytest.mark.parametrize("case", sorted(ERROR_CASES))
def test_each_error_rule(tmp_path: Path, case: str) -> None:
    mutate, code = ERROR_CASES[case]
    assert code in _codes(_issues(tmp_path, mutate), "error")


def test_wrong_answer_key_is_a_schema_error(tmp_path: Path) -> None:
    issues = _issues(tmp_path, lambda f: _lesson(f)["activities"][0].update(correct=["z"]))
    assert "schema" in _codes(issues, "error")


def test_absolute_rule_is_a_warning(tmp_path: Path) -> None:
    issues = _issues(
        tmp_path,
        lambda f: _lesson(f)["pcre"]["rules"].append(
            {"text": "You must always use from.", "source": "cambridge-prepositions"}
        ),
    )
    assert "absolute_rule" in _codes(issues, "warning")
    assert not _codes(issues, "error")


def test_rule_without_source_and_length_are_warnings(tmp_path: Path) -> None:
    def mutate(f: dict[str, Any]) -> None:
        _lesson(f)["pcre"]["rules"].append({"text": "To marca el final."})
        _lesson(f)["passages"][0]["text_en"] = "Too short passage."
        for act in _lesson(f)["activities"]:
            act["stimulus"] = {"passage": "p1"}

    warnings = _codes(_issues(tmp_path, mutate), "warning")
    assert {"rule_without_source", "length_out_of_range"} <= warnings


def test_pending_audio_is_a_warning_and_reviewed_audio_is_clean(tmp_path: Path) -> None:
    pending = _issues(tmp_path / "a", lambda f: add_listening(f, reviewed=False))
    assert "pending_audio" in _codes(pending, "warning")
    assert not _codes(pending, "error")
    ready = _issues(tmp_path / "b", lambda f: add_listening(f, reviewed=True))
    assert "pending_audio" not in _codes(ready, "warning")
    assert not _codes(ready, "error")


def test_fake_provider_audio_is_rejected(tmp_path: Path) -> None:
    def mutate(f: dict[str, Any]) -> None:
        add_listening(f, reviewed=True)
        f["audio/manifest.yaml"]["audio"][0]["provider"] = "fake"

    assert "audio_provider" in _codes(_issues(tmp_path, mutate), "error")


def test_initial_form_needs_exact_distribution(tmp_path: Path) -> None:
    def mutate(f: dict[str, Any]) -> None:
        form = dict(f["units/u1/checkpoint.yaml"])
        form.update(slug="inicial", form_kind="initial", position=1)
        form.pop("unit")
        form["activities"] = [
            dict(a, key=a["key"].replace("u1.cp", "ini")) for a in form["activities"]
        ]
        f["assessments/inicial.yaml"] = form

    issues = _issues(tmp_path, mutate)
    assert any(i.code == "minimum_items" and "inicial" in i.file for i in issues)
