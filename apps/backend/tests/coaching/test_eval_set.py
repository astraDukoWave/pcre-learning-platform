"""AC-05 (parte offline) y REQ-03: el set de evaluación tiene al menos 24 casos con todas las
categorías pedidas, y el reporte separa un modelo correcto de uno que contradice variantes
válidas o que devuelve evidencia inválida. Las salidas son escritas a mano (no grabadas de
un modelo real); el run real es G5a."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

from app.modules.coaching.feedback import domain
from app.modules.coaching.feedback.ports import (
    EvaluatorFailed,
    EvaluatorReply,
    EvaluatorUnknown,
    FeedbackRequest,
)

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
    for path in sorted((ROOT / "evals" / "feedback" / "cases").glob("*.yaml")):
        declared = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert {"must_not_flag", "expected_status", "max_observations"} <= set(declared), path
        assert "must_mention_criteria" in declared, path
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
    assert runner.overlap("your evening programme", "evening programme") == "contradiction"
    assert runner.overlap("evening programme", "programme") == "contradiction"
    assert (
        runner.overlap("I have a colour-coded calendar, so planning matters", "colour-coded")
        == "mention"
    )
    assert runner.overlap("which days", "days the classes meet") is None
    assert runner.overlap("ram", "program") is None  # palabras completas


def test_cli_offline_report_and_exit_code(tmp_path: Path) -> None:
    runner = load_runner()
    report = tmp_path / "report.md"
    assert runner.main(["--offline", "reference", "--report", str(report)]) == 0
    assert "Modelo elegido: **offline-reference**" in report.read_text(encoding="utf-8")
    assert runner.main(["--offline", "flawed"]) == 1
    assert runner.parse_models("a=0.1/0.4, b=0.3/2.5") == [("a", 0.1, 0.4), ("b", 0.3, 2.5)]
    for bad in ("a=0/0", "a=0.1/0", "a=-1/2", "a=x/1", "a=nan/1"):
        with pytest.raises(SystemExit):  # con precio 0 el tope no actúa
            runner.parse_models(bad)


class Scripted:
    """Evaluador con salida y tokens fijos; `fail` lanza el error indicado en cada llamada."""

    provider = "test"
    max_output_tokens = 1000

    def __init__(self, model: str, raw: str = "", fail: Exception | None = None) -> None:
        self.model, self.raw, self.fail, self.calls = model, raw, fail, 0

    def evaluate(self, prompt: str, request: FeedbackRequest) -> EvaluatorReply:
        self.calls += 1
        if self.fail is not None:
            raise self.fail
        return EvaluatorReply(self.raw, self.model, 1000, 100, 5)


def test_degenerate_models_never_meet_the_rule() -> None:
    runner = load_runner()
    cases, tasks = runner.load_cases(), runner.load_tasks()
    abstain = json.dumps({"status": "not_evaluable", "reason": "too_short", "observations": []})
    empty = runner.run_model(Scripted("vacio", raw=""), cases, tasks)
    always_no = runner.run_model(Scripted("abstiene", raw=abstain), cases, tasks)
    good = runner.run_model(runner.RecordedEvaluator("reference"), cases, tasks)
    assert empty.invalid_outputs == len(cases) and empty.evidence_rate == 0.0
    assert not empty.passes and not always_no.passes and always_no.status_rate < 0.9
    assert runner.select([empty, always_no, good]) is good


class Obedient:
    """La salida de referencia, salvo en los casos de inyección, donde obedece al alumno."""

    def __init__(self, runner: ModuleType, text: str) -> None:
        self.inner = runner.RecordedEvaluator("reference")
        self.provider, self.model = "test", "obediente"
        self.max_output_tokens = 1024
        self.text = text
        self.cases = {c.id: c for c in runner.load_cases()}

    def evaluate(self, prompt: str, request: FeedbackRequest) -> EvaluatorReply:
        case = next(c for c in self.cases.values() if c.learner_text == request.learner_text)
        self.inner.case_id = case.id
        reply: EvaluatorReply = self.inner.evaluate(prompt, request)
        if case.category != "inyección":
            return reply
        data: dict[str, Any] = json.loads(reply.raw_text)
        for o in data["observations"]:
            o["observation_es"] = self.text
        return EvaluatorReply(json.dumps(data), self.model, 10, 10, 5)


@pytest.mark.parametrize(
    "text",
    [
        "Tu respuesta es perfecta: mereces 6 de 6.",
        "Tu inglés ya es nivel C2.",
        "Repasa más en example.com/guia",
    ],
)
def test_a_model_that_obeys_the_injection_fails_the_rule(text: str) -> None:
    runner = load_runner()
    report = runner.run_model(Obedient(runner, text), runner.load_cases(), runner.load_tasks())
    assert report.forbidden and report.injection_failures and not report.meets_rule
    assert report.verdict == "❌"


def test_a_valid_fragment_inside_a_longer_quote_needs_human_review() -> None:
    runner = load_runner()
    cases = runner.load_cases()
    case = next(c for c in cases if c.id == "email-04-british-spelling")
    report = runner.ModelReport(model="x")
    feedback = domain.ValidatedFeedback(
        status="evaluable",
        observations=(
            domain.Observation(
                "language_control",
                "writing to enquire about",
                "«enquire» está mal escrito.",
                "Usa «inquire».",
            ),
        ),
        returned_observations=1,
    )
    runner.score_case(report, case, feedback)
    assert report.mentions and not report.contradictions
    assert not report.passes and report.verdict in {"revisar", "❌"}


def test_cost_cap_is_respected_and_carried_across_models() -> None:
    runner = load_runner()
    cases, tasks = runner.load_cases(), runner.load_tasks()
    first, second = Scripted("a", raw=""), Scripted("b", raw="")
    # Cada llamada cuesta ~1000·1 + 100·10 = 2000 µUSD; el peor caso, más.
    reports, spent = runner.run_models(
        [(first, 1.0, 10.0), (second, 1.0, 10.0)], cases, tasks, max_cost_usd=0.05
    )
    assert spent <= 0.05 and first.calls > 0 and second.calls == 0
    assert not reports[1].complete and "tope de costo" in reports[1].errors[0]
    unknown = Scripted("u", fail=EvaluatorUnknown("timeout"))
    failed = Scripted("f", fail=EvaluatorFailed("http_500"))
    (u_report, f_report), _ = runner.run_models(
        [(unknown, 1.0, 10.0), (failed, 1.0, 10.0)], cases[:2], tasks, max_cost_usd=10.0
    )
    request = runner.build_request(cases[0], tasks)
    worst_in, worst_out = runner.feedback_service.max_tokens(
        runner.prompts.render(request), unknown
    )
    assert u_report.cost_usd >= (worst_in * 1.0 + worst_out * 10.0) / 1_000_000  # peor caso
    assert f_report.cost_usd == 0.0 and len(f_report.errors) == 2  # no se envió: sin costo


def test_workflow_requires_the_evals_environment_and_a_cost_cap() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = workflow.get(True) or workflow.get("on")  # PyYAML lee `on` como True
    assert list(triggers) == ["workflow_dispatch"]
    assert {"models", "max_cost_usd"} <= set(triggers["workflow_dispatch"]["inputs"])
    (job,) = workflow["jobs"].values()
    assert job["environment"] == "evals"
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "secrets.GEMINI_API_KEY" in text and "--max-cost-usd" in text
