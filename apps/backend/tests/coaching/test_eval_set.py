"""AC-05 (parte offline) y REQ-03: el set de evaluación tiene al menos 24 casos con todas las
categorías pedidas, y el reporte separa un modelo correcto de uno que contradice variantes
válidas o que devuelve evidencia inválida. Las salidas son escritas a mano (no grabadas de
un modelo real); el run real es G5a."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import yaml

from app.modules.coaching.feedback import domain

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "evals" / "run.py"
WORKFLOW = ROOT / ".github" / "workflows" / "feedback-eval.yml"


def load_runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("feedback_eval_run", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # las dataclasses del script lo necesitan
    spec.loader.exec_module(module)
    return module


def test_cases_cover_the_required_categories_and_tasks() -> None:
    runner = load_runner()
    cases = runner.load_cases()
    assert len(cases) >= 24
    categories = {c.category for c in cases}
    assert {
        "correcta",
        "incorrecta",
        "variante válida",
        "demasiado corta",
        "fuera de tema",
        "en español",
        "inyección",
        "con URL",
        "casi vacía",
    } <= categories
    assert {c.task for c in cases} == {"u1-email", "dx-discussion", "u1-interview"}
    for case in cases:
        for fragment in case.must_not_flag:  # lo válido existe literalmente en el texto
            assert domain.evidence_in(fragment, case.learner_text), (case.id, fragment)


def test_reference_outputs_pass_the_selection_rule() -> None:
    runner = load_runner()
    report = runner.run_model(
        runner.RecordedEvaluator("reference"), runner.load_cases(), runner.load_tasks()
    )
    assert report.passes and report.contradictions == []
    assert report.status_matches == report.cases and report.missing_mentions == []
    assert report.evidence_rate == 1.0


def test_adversarial_outputs_are_cleaned_and_fail_the_rule() -> None:
    runner = load_runner()
    cases = runner.load_cases()
    tasks = runner.load_tasks()
    evaluator = runner.RecordedEvaluator("adversarial")
    for case in cases:
        evaluator.case_id = case.id
        feedback = runner.feedback_service.evaluate(
            evaluator, runner.build_request(case, tasks)
        ).feedback
        for o in feedback.observations:  # nada de lo que sobrevive trae basura
            assert domain.evidence_in(o.evidence, case.learner_text)
            assert not domain.URL.search(o.suggestion_es + o.observation_es)
            assert not domain.EXAM_SCORE.search(o.suggestion_es + o.observation_es)
    report = runner.run_model(runner.RecordedEvaluator("adversarial"), cases, tasks)
    assert report.invalid_outputs == 3 and report.evidence_rate < runner.MIN_EVIDENCE
    assert not report.passes


def test_contradicting_valid_variants_fails_the_rule_and_selection() -> None:
    runner = load_runner()
    cases, tasks = runner.load_cases(), runner.load_tasks()
    flawed = runner.run_model(runner.RecordedEvaluator("flawed"), cases, tasks)
    good = runner.run_model(runner.RecordedEvaluator("reference"), cases, tasks)
    assert len(flawed.contradictions) == 4 and not flawed.passes
    assert runner.select([flawed, good]) is good
    assert runner.overlap("programme", "programme") == "contradiction"
    assert (
        runner.overlap("I have a colour-coded calendar, so planning matters", "colour-coded")
        == "mention"
    )


def test_cli_offline_report_and_exit_code(tmp_path: Path) -> None:
    runner = load_runner()
    report = tmp_path / "report.md"
    assert runner.main(["--offline", "reference", "--report", str(report)]) == 0
    assert "Modelo elegido: **offline-reference**" in report.read_text(encoding="utf-8")
    assert runner.main(["--offline", "flawed"]) == 1
    assert runner.parse_models("a=0.1/0.4, b=0.3/2.5") == [("a", 0.1, 0.4), ("b", 0.3, 2.5)]


def test_workflow_requires_the_evals_environment_and_a_cost_cap() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = workflow.get(True) or workflow.get("on")  # PyYAML lee `on` como True
    assert list(triggers) == ["workflow_dispatch"]
    assert {"models", "max_cost_usd"} <= set(triggers["workflow_dispatch"]["inputs"])
    (job,) = workflow["jobs"].values()
    assert job["environment"] == "evals"
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "secrets.GEMINI_API_KEY" in text and "--max-cost-usd" in text
