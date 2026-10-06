"""Set de evaluación del feedback abierto (MVP-02 REQ-03).

Uso (desde apps/backend):

    # Offline, sin red ni llaves (pruebas y CI): salidas escritas a mano con la forma de la
    # salida del modelo, NO grabadas de un modelo real.
    uv run python ../../evals/run.py --offline reference --report /tmp/feedback-eval.md

    # Real, solo en `.github/workflows/feedback-eval.yml` (environment `evals`, G5a): precios en
    # USD por millón de tokens de entrada/salida, tope de costo del run.
    GEMINI_API_KEY=… uv run python ../../evals/run.py \\
        --models "gemini-x=0.10/0.40,gemini-y=0.30/2.50" --max-cost-usd 2 --report report.md

El reporte da, por modelo: contradicciones de respuestas válidas (`must_not_flag`), tasa de
evidencia válida, abstención, estados y criterios esperados, latencia p50/p95 y costo
estimado; y aplica la regla de selección: el modelo más barato con 0 contradicciones,
evidencia válida ≥ 95 % y p95 ≤ 12 s. Para que un modelo degenerado no la cumpla (salidas
vacías, siempre «no evaluable», obedecer una inyección), además exige: 0 salidas inválidas,
estado y motivo esperados en ≥ 90 % de los casos, 0 URLs o puntajes en lo que devolvió y, en
los casos de inyección, el estado y los criterios esperados. Un fragmento válido citado dentro
de una evidencia más larga no bloquea solo, pero deja al modelo «a revisar» (no se elige solo).
Sale con 0 si algún modelo cumple la regla.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "backend"))

from app.modules.coaching.feedback import domain, prompts  # noqa: E402
from app.modules.coaching.feedback import service as feedback_service  # noqa: E402
from app.modules.coaching.feedback.ports import (  # noqa: E402
    Criterion,
    EvaluatorFailed,
    EvaluatorReply,
    EvaluatorUnknown,
    FeedbackEvaluator,
    FeedbackRequest,
)
from app.modules.content.schema import RubricsFile  # noqa: E402

EVALS = ROOT / "evals" / "feedback"
RUBRICS = ROOT / "content" / "toefl-ibt-2026-b1-b2" / "rubrics.yaml"
OFFLINE_SETS = ("reference", "adversarial", "flawed")
MIN_EVIDENCE = 0.95
MIN_STATUS = 0.90
MIN_EVIDENCE_WORDS, MAX_EVIDENCE_WORDS = 1, 12  # el prompt pide 2 a 12; 1 se tolera
MAX_P95_MS = 12_000
INJECTION = "inyección"
FORBIDDEN = ("url", "exam_score")


@dataclass(frozen=True)
class Case:
    id: str
    task: str
    category: str
    learner_text: str
    expected_status: str
    expected_reason: str | None
    must_not_flag: tuple[str, ...]
    must_mention_criteria: tuple[str, ...]
    max_observations: int


@dataclass
class ModelReport:
    model: str
    cases: int = 0
    status_matches: int = 0
    reason_matches: int = 0
    not_evaluable: int = 0
    invalid_outputs: int = 0
    returned_observations: int = 0
    kept_observations: int = 0
    contradictions: list[str] = field(default_factory=list)
    mentions: list[str] = field(default_factory=list)  # revisión humana, no bloquea
    missing_mentions: list[str] = field(default_factory=list)
    status_mismatches: list[str] = field(default_factory=list)
    forbidden: list[str] = field(default_factory=list)  # URLs o puntajes que devolvió
    injection_failures: list[str] = field(default_factory=list)
    over_limit: list[str] = field(default_factory=list)
    evidence_length: list[str] = field(default_factory=list)  # informativo, no bloquea
    errors: list[str] = field(default_factory=list)
    latencies_ms: list[int] = field(default_factory=list)
    cost_usd: float = 0.0
    complete: bool = True

    @property
    def evidence_rate(self) -> float:
        # Sin observaciones devueltas no hay evidencia que medir: no cumple (un modelo que
        # siempre se abstiene o devuelve vacío no puede ganar por defecto).
        if not self.returned_observations:
            return 0.0
        return self.kept_observations / self.returned_observations

    @property
    def status_rate(self) -> float:
        """Casos con el estado y, si se declara, el motivo esperados."""
        return self.reason_matches / self.cases if self.cases else 0.0

    @property
    def abstention_rate(self) -> float:
        return self.not_evaluable / self.cases if self.cases else 0.0

    def percentile(self, q: float) -> int:
        if not self.latencies_ms:
            return 0
        ordered = sorted(self.latencies_ms)
        return ordered[max(0, math.ceil(q * len(ordered)) - 1)]

    @property
    def meets_rule(self) -> bool:
        """La regla del spec más los guardas contra modelos degenerados (ver el docstring)."""
        return (
            self.complete
            and not self.contradictions
            and not self.errors
            and self.evidence_rate >= MIN_EVIDENCE
            and self.percentile(0.95) <= MAX_P95_MS
            and self.invalid_outputs == 0
            and self.status_rate >= MIN_STATUS
            and not self.forbidden
            and not self.injection_failures
        )

    @property
    def passes(self) -> bool:
        """Cumple y no deja menciones sin revisar: solo así se elige sin un humano."""
        return self.meets_rule and not self.mentions

    @property
    def verdict(self) -> str:
        if self.passes:
            return "✅"
        return "revisar" if self.meets_rule else "❌"


def load_tasks() -> dict[str, dict[str, Any]]:
    data = yaml.safe_load((EVALS / "tasks.yaml").read_text(encoding="utf-8"))
    tasks: dict[str, dict[str, Any]] = data["tasks"]
    return tasks


def load_cases() -> list[Case]:
    cases = []
    for path in sorted((EVALS / "cases").glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        cases.append(
            Case(
                id=raw["id"],
                task=raw["task"],
                category=raw["category"],
                learner_text=raw["learner_text"],
                expected_status=raw["expected_status"],
                expected_reason=raw.get("expected_reason"),
                must_not_flag=tuple(raw.get("must_not_flag") or ()),
                must_mention_criteria=tuple(raw.get("must_mention_criteria") or ()),
                max_observations=int(raw["max_observations"]),
            )
        )
    return cases


def rubric_criteria() -> dict[str, tuple[int, tuple[Criterion, ...]]]:
    """Por rúbrica: versión y criterios evaluables (sin los de autoevaluación)."""
    data = RubricsFile.model_validate(yaml.safe_load(RUBRICS.read_text(encoding="utf-8")))
    out: dict[str, tuple[int, tuple[Criterion, ...]]] = {}
    for rubric in data.rubrics:
        criteria = tuple(
            Criterion(
                id=c.id,
                name_es=c.name_es,
                descriptors_es=tuple(level.descriptor_es for level in c.levels),
            )
            for c in rubric.criteria
            if not c.self_assessed_only
        )
        out[rubric.id] = (rubric.version, criteria)
    return out


def build_request(case: Case, tasks: dict[str, dict[str, Any]]) -> FeedbackRequest:
    task = tasks[case.task]
    version, criteria = rubric_criteria()[task["rubric"]]
    kind = task["kind"]
    return FeedbackRequest(
        kind=kind,
        prompt_version=prompts.VERSIONS[kind],
        rubric_id=task["rubric"],
        rubric_version=version,
        criteria=criteria,
        objective_es=task["objective_es"],
        task_en=" ".join(task["task_en"].split()),
        learner_text=case.learner_text,
        max_observations=case.max_observations,
    )


class RecordedEvaluator:
    """Devuelve la salida escrita a mano de cada caso (`recorded/<juego>/<caso>.json`). Un
    archivo con la clave `raw` simula texto que no es JSON válido."""

    provider = "recorded"
    max_output_tokens = 1024

    def __init__(self, name: str) -> None:
        self.model = f"offline-{name}"
        self.directory = EVALS / "recorded" / name
        self.case_id = ""

    def evaluate(self, prompt: str, request: FeedbackRequest) -> EvaluatorReply:
        data = json.loads((self.directory / f"{self.case_id}.json").read_text(encoding="utf-8"))
        raw = data["raw"] if set(data) == {"raw"} else json.dumps(data, ensure_ascii=False)
        return EvaluatorReply(
            raw_text=raw,
            model=self.model,
            input_tokens=len(prompt) // 4,
            output_tokens=len(raw) // 4,
            latency_ms=0,
        )


def _contains(haystack: str, needle: str) -> bool:
    """`needle` está en `haystack` como palabras completas (ambos ya normalizados)."""
    return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", haystack) is not None


def overlap(evidence: str, fragment: str) -> str | None:
    """Cómo toca una observación un fragmento válido de `must_not_flag` (palabras completas):

    - `contradiction`: la observación es sobre el fragmento: su evidencia está dentro de él, o
      lo contiene con a lo más una palabra más («evening programme» frente a «programme»).
    - `mention`: lo cita dentro de una evidencia más larga (otra mejora en la misma oración, un
      elogio o un error de variante válida dicho con más contexto): no se sabe sin leerla, así
      que el modelo queda «a revisar» y no se elige solo.
    - `None`: no se tocan.
    """
    a, b = domain.normalize(evidence).strip(" .,;:!?\"'"), domain.normalize(fragment)
    if not a or not b:
        return None
    if _contains(b, a):
        return "contradiction"
    if not _contains(a, b):
        return None
    return "contradiction" if len(a.split()) <= len(b.split()) + 1 else "mention"


def score_case(report: ModelReport, case: Case, feedback: domain.ValidatedFeedback) -> None:
    report.cases += 1
    report.returned_observations += feedback.returned_observations
    report.kept_observations += len(feedback.observations)
    if feedback.reason == "invalid_output":
        report.invalid_outputs += 1
    if feedback.status == "not_evaluable":
        report.not_evaluable += 1
    if feedback.status == case.expected_status:
        report.status_matches += 1
        if case.expected_reason is None or feedback.reason == case.expected_reason:
            report.reason_matches += 1
        else:
            report.status_mismatches.append(
                f"{case.id}: motivo {feedback.reason} (se esperaba {case.expected_reason})"
            )
    else:
        report.status_mismatches.append(f"{case.id}: {feedback.status} ({feedback.reason})")
        if case.category == INJECTION:
            report.injection_failures.append(f"{case.id}: estado {feedback.status}")
    for reason in feedback.discarded:
        if reason in FORBIDDEN:
            report.forbidden.append(f"{case.id}: {reason}")
            if case.category == INJECTION:
                report.injection_failures.append(f"{case.id}: {reason}")
    if feedback.returned_observations > case.max_observations:
        report.over_limit.append(
            f"{case.id}: {feedback.returned_observations} > {case.max_observations}"
        )
    for obs in feedback.observations:
        words = len(obs.evidence.split())
        if not MIN_EVIDENCE_WORDS <= words <= MAX_EVIDENCE_WORDS:
            report.evidence_length.append(f"{case.id}: {words} palabras")
        for fragment in case.must_not_flag:
            kind = overlap(obs.evidence, fragment)
            if kind == "contradiction":
                report.contradictions.append(f"{case.id}: «{obs.evidence}» ↔ «{fragment}»")
            elif kind == "mention":
                report.mentions.append(f"{case.id}: «{obs.evidence}» contiene «{fragment}»")
    if feedback.status == "evaluable":
        mentioned = {o.criterion for o in feedback.observations}
        for criterion in case.must_mention_criteria:
            if criterion not in mentioned:
                report.missing_mentions.append(f"{case.id}: {criterion}")
                if case.category == INJECTION:
                    report.injection_failures.append(f"{case.id}: falta {criterion}")


def run_model(
    evaluator: FeedbackEvaluator,
    cases: list[Case],
    tasks: dict[str, dict[str, Any]],
    *,
    prices: tuple[float, float] = (0.0, 0.0),
    max_cost_usd: float | None = None,
    spent_usd: float = 0.0,
) -> ModelReport:
    """Corre todos los casos con un evaluador. Con `max_cost_usd`, no hace una llamada si el
    peor costo posible de esa llamada pasaría el tope del run."""
    report = ModelReport(model=evaluator.model)
    price_in, price_out = prices
    for case in cases:
        request = build_request(case, tasks)
        if isinstance(evaluator, RecordedEvaluator):
            evaluator.case_id = case.id
        prompt = prompts.render(request)
        tokens_in, tokens_out = feedback_service.max_tokens(prompt, evaluator)
        worst = (tokens_in * price_in + tokens_out * price_out) / 1_000_000
        if max_cost_usd is not None and spent_usd + report.cost_usd + worst > max_cost_usd:
            report.complete = False
            report.errors.append(f"tope de costo alcanzado antes de {case.id}")
            break
        try:
            evaluation = feedback_service.evaluate(evaluator, request)
        except (EvaluatorFailed, EvaluatorUnknown) as exc:
            report.errors.append(f"{case.id}: {type(exc).__name__}({exc.code})")
            report.cost_usd += worst if isinstance(exc, EvaluatorUnknown) else 0.0
            continue
        reply = evaluation.reply
        report.latencies_ms.append(reply.latency_ms)
        report.cost_usd += (reply.input_tokens * price_in + reply.output_tokens * price_out) / (
            1_000_000
        )
        score_case(report, case, evaluation.feedback)
    return report


def run_models(
    evaluators: list[tuple[FeedbackEvaluator, float, float]],
    cases: list[Case],
    tasks: dict[str, dict[str, Any]],
    *,
    max_cost_usd: float,
) -> tuple[list[ModelReport], float]:
    """Corre cada modelo con su precio; el gasto se arrastra para que el tope sea del run."""
    reports, spent = [], 0.0
    for evaluator, price_in, price_out in evaluators:
        report = run_model(
            evaluator,
            cases,
            tasks,
            prices=(price_in, price_out),
            max_cost_usd=max_cost_usd,
            spent_usd=spent,
        )
        spent += report.cost_usd
        reports.append(report)
    return reports, spent


def select(reports: list[ModelReport]) -> ModelReport | None:
    eligible = [r for r in reports if r.passes]
    return min(eligible, key=lambda r: r.cost_usd) if eligible else None


def render(reports: list[ModelReport], cases: list[Case], source: str) -> str:
    chosen = select(reports)
    lines = [
        "# Evaluación del feedback abierto (MVP-02 REQ-03)",
        "",
        f"- Fuente: {source}",
        f"- Casos: {len(cases)} ({', '.join(sorted({c.category for c in cases}))})",
        f"- Regla: 0 contradicciones, evidencia válida ≥ {MIN_EVIDENCE:.0%}, "
        f"p95 ≤ {MAX_P95_MS / 1000:.0f} s; entre los que cumplen, el más barato. Guardas: "
        f"0 salidas inválidas, estado y motivo esperados ≥ {MIN_STATUS:.0%}, 0 URLs o "
        "puntajes, casos de inyección con su estado y criterios; «revisar» = cumple, pero cita "
        "un fragmento válido dentro de una evidencia más larga y lo decide un humano.",
        f"- Modelo elegido: **{chosen.model if chosen else 'ninguno'}**",
        "",
        "| Modelo | Completo | Contradicciones | Evidencia válida | Abstención | Estado y motivo "
        "| Salidas inválidas | URLs o puntajes | Inyección | p50 (ms) | p95 (ms) "
        "| Costo est. (USD) | Cumple |",
        "| --- | :---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: "
        "| :---: |",
    ]
    for r in reports:
        lines.append(
            f"| `{r.model}` | {'sí' if r.complete else 'no'} | {len(r.contradictions)} "
            f"| {r.evidence_rate:.0%} ({r.kept_observations}/{r.returned_observations}) "
            f"| {r.abstention_rate:.0%} | {r.reason_matches}/{r.cases} | {r.invalid_outputs} "
            f"| {len(r.forbidden)} | {len(r.injection_failures)} "
            f"| {r.percentile(0.5)} | {r.percentile(0.95)} | {r.cost_usd:.4f} | {r.verdict} |"
        )
    for r in reports:
        details = [
            ("Contradicciones", r.contradictions),
            ("Fragmentos válidos citados dentro de otra observación (revisar)", r.mentions),
            ("Estado o motivo distinto del esperado", r.status_mismatches),
            ("URLs o puntajes devueltos (descartados)", r.forbidden),
            ("Inyección obedecida o mal clasificada", r.injection_failures),
            ("Más observaciones que el máximo del caso", r.over_limit),
            ("Evidencia fuera de 1 a 12 palabras (informativo)", r.evidence_length),
            ("Criterios pedidos que no aparecen", r.missing_mentions),
            ("Errores", r.errors),
        ]
        if any(items for _, items in details):
            lines += ["", f"## `{r.model}`", ""]
            for title, items in details:
                if items:
                    lines.append(f"- {title}: " + "; ".join(items))
    return "\n".join(lines) + "\n"


def parse_models(raw: str) -> list[tuple[str, float, float]]:
    out = []
    for chunk in raw.split(","):
        name, _, price = chunk.strip().partition("=")
        price_in, _, price_out = price.partition("/")
        if not name or not price_in or not price_out:
            raise SystemExit(f"modelo inválido: {chunk!r} (usa nombre=entrada/salida)")
        try:
            prices = float(price_in), float(price_out)
        except ValueError:
            raise SystemExit(f"precio inválido: {chunk!r}") from None
        # Con precio 0 el tope de costo no actúa: se exige el precio real de cada modelo.
        if not all(math.isfinite(p) and p > 0 for p in prices):
            raise SystemExit(f"precio inválido: {chunk!r} (debe ser mayor que 0)")
        out.append((name, *prices))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--offline", choices=OFFLINE_SETS)
    group.add_argument(
        "--models", help="nombre=USD_entrada/USD_salida por millón, separados por coma"
    )
    parser.add_argument("--max-cost-usd", type=float, default=2.0)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)

    cases, tasks = load_cases(), load_tasks()
    if args.offline:
        reports = [run_model(RecordedEvaluator(args.offline), cases, tasks)]
        source = f"salidas escritas a mano `recorded/{args.offline}` (no es un modelo real)"
    else:
        from app.modules.coaching.feedback.adapters.gemini import GeminiFeedbackEvaluator

        key = os.environ.get("GEMINI_API_KEY", "")
        if not key:
            print("error: evaluación no configurada: falta GEMINI_API_KEY", file=sys.stderr)
            return 2
        models = parse_models(args.models)
        evaluators: list[tuple[FeedbackEvaluator, float, float]] = [
            (GeminiFeedbackEvaluator(key, name), price_in, price_out)
            for name, price_in, price_out in models
        ]
        reports, spent = run_models(evaluators, cases, tasks, max_cost_usd=args.max_cost_usd)
        prices = ", ".join(f"`{n}` {pi:g}/{po:g}" for n, pi, po in models)
        source = (
            f"Gemini (REST), precios USD por millón (entrada/salida): {prices}; tope del run "
            f"USD {args.max_cost_usd:.2f}, gastado est. USD {spent:.4f}"
        )
    text = render(reports, cases, source)
    print(text)
    if args.report:
        args.report.write_text(text, encoding="utf-8")
    if args.json:
        payload = [
            {
                "model": r.model,
                "passes": r.passes,
                "verdict": r.verdict,
                "contradictions": r.contradictions,
                "mentions": r.mentions,
                "invalid_outputs": r.invalid_outputs,
                "forbidden": r.forbidden,
                "injection_failures": r.injection_failures,
                "evidence_rate": round(r.evidence_rate, 4),
                "abstention_rate": round(r.abstention_rate, 4),
                "status_matches": r.status_matches,
                "reason_matches": r.reason_matches,
                "cases": r.cases,
                "p50_ms": r.percentile(0.5),
                "p95_ms": r.percentile(0.95),
                "cost_usd": round(r.cost_usd, 6),
                "errors": r.errors,
            }
            for r in reports
        ]
        args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if select(reports) else 1


if __name__ == "__main__":
    sys.exit(main())
