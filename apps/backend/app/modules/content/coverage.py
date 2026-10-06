"""`docs/contenido/cobertura.md` (contrato §10): matriz familia × pool, conteos por objetivo
y por formato, lo pendiente y el estado editorial del archivo. Determinista: mismo
contenido, mismo archivo, byte a byte (la CI lo regenera y compara)."""

from __future__ import annotations

from collections import defaultdict

from app.modules.content.lint import unit_number
from app.modules.content.loader import ContentBundle, Issue
from app.modules.content.schema import FAMILY_FORMATS, AssessmentFormFile, LessonFile, ScenarioFile

POOLS = ("practice", "review", "assessment")
FORMATS = (
    "choice",
    "word_completion",
    "sentence_order",
    "short_writing",
    "recorded_speaking",
    "guided_dialogue",
)
PENDING = "pendiente"


def render_coverage(bundle: ContentBundle, issues: list[Issue]) -> str:
    assert bundle.path is not None and bundle.objectives is not None
    items = bundle.valid_items
    lessons = [i for i in items if isinstance(i, LessonFile)]
    scenarios = [i for i in items if isinstance(i, ScenarioFile)]
    forms = [i for i in items if isinstance(i, AssessmentFormFile)]
    checkpoints = [f for f in forms if f.form_kind == "checkpoint"]
    path_forms = [f for f in forms if f.form_kind != "checkpoint"]
    units_total = len(bundle.path.units)
    units_with = {getattr(i, "unit", None) for i in items} - {None}
    errors = sum(1 for i in issues if i.severity == "error")
    warnings = len(issues) - errors

    by_family: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    by_objective: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_format: dict[str, int] = defaultdict(int)
    for item in items:
        for act in item.activities:
            by_family[act.task_family][act.pool].append(act.key)
            by_format[act.format] += 1
            for code in act.objectives:
                by_objective[code][act.pool] += 1

    out: list[str] = []
    out.append(f"# Cobertura de contenido — `{bundle.path.code}`\n")
    out.append(
        "> Generado por `make content-lint` (contrato curricular §10). No se edita a mano: la CI\n"
        "> lo regenera y falla si hay diferencias. El estado `published` se lee en el panel.\n"
    )
    out.append("## Resumen\n")
    out.append(f"- Unidades con contenido: {len(units_with)} de {units_total}")
    out.append(f"- Lecciones: {len(lessons)} de {units_total * 4}")
    out.append(f"- Escenarios: {len(scenarios)} de {units_total}")
    out.append(f"- Checkpoints: {len(checkpoints)} de {units_total}")
    out.append(f"- Formularios de ruta (inicial y final): {len(path_forms)} de 2")
    out.append(f"- Lint: {errors} errores · {warnings} advertencias\n")

    out.append("## Familia × pool\n")
    out.append("| Familia | Formato | practice | review | assessment |")
    out.append("|---|---|---|---|---|")
    for family in sorted(FAMILY_FORMATS):
        cells = []
        for pool in POOLS:
            keys = sorted(by_family[family][pool])
            cells.append(", ".join(f"`{k}`" for k in keys) if keys else PENDING)
        fmt = "/".join(FAMILY_FORMATS[family])
        out.append(f"| `{family}` | {fmt} | " + " | ".join(cells) + " |")
    out.append("")

    out.append("## Por objetivo\n")
    out.append("| Objetivo | Descripción | practice | review | assessment | Estado |")
    out.append("|---|---|---|---|---|---|")
    for obj in sorted(bundle.objectives.objectives, key=lambda o: (o.unit, o.code)):
        counts = by_objective.get(obj.code, {})
        p, r, a = (counts.get(pool, 0) for pool in POOLS)
        state = "con práctica y comprobación" if p and a else PENDING
        desc = obj.description_es.replace("|", "/")
        out.append(f"| `{obj.code}` | {desc} | {p} | {r} | {a} | {state} |")
    out.append("")

    out.append("## Por formato\n")
    out.append("| Formato | Actividades |")
    out.append("|---|---|")
    for fmt in FORMATS:
        out.append(f"| `{fmt}` | {by_format.get(fmt, 0)} |")
    out.append("")

    out.append("## Estado editorial por ítem (archivo)\n")
    if items:
        out.append("| Ítem | Tipo | Unidad | Actividades | Estado del archivo |")
        out.append("|---|---|---|---|---|")
        for loaded in sorted(bundle.items, key=lambda x: x.file):
            model = loaded.model
            if model is None:
                out.append(f"| `{loaded.file}` | inválido | — | — | error de esquema |")
                continue
            is_form = isinstance(model, AssessmentFormFile)
            kind = f"form:{model.form_kind}" if is_form else model.kind  # type: ignore[union-attr]
            unit = getattr(model, "unit", None) or "ruta"
            out.append(
                f"| `{model.slug}` | {kind} | {unit} | {len(model.activities)} | {model.status} |"
            )
    else:
        out.append("Aún no hay ítems de contenido.")
    out.append("")

    out.append("## Pendiente\n")
    pending: list[str] = []
    for unit in sorted(bundle.path.units, key=lambda u: u.position):
        n = unit_number(unit.slug)
        unit_lessons = {i.skill for i in lessons if i.unit == unit.slug}
        missing = [
            s for s in ("reading", "listening", "writing", "speaking") if s not in unit_lessons
        ]
        parts = []
        if missing:
            parts.append("lecciones de " + ", ".join(missing))
        if not any(s.unit == unit.slug for s in scenarios):
            parts.append("escenario")
        if not any(c.unit == unit.slug for c in checkpoints):
            parts.append("checkpoint")
        if parts:
            pending.append(f"- U{n} · {unit.title}: " + "; ".join(parts))
    for kind in ("initial", "final"):
        if not any(f.form_kind == kind for f in path_forms):
            label = "diagnóstico inicial" if kind == "initial" else "formulario final"
            pending.append(f"- Ruta: {label}")
    for family in sorted(FAMILY_FORMATS):
        if not by_family[family]["practice"] or not by_family[family]["assessment"]:
            have = [p for p in POOLS if by_family[family][p]]
            pending.append(
                f"- Familia `{family}`: falta en "
                + ", ".join(p for p in ("practice", "assessment") if p not in have)
            )
    out += pending or ["Nada pendiente."]
    out.append("")

    warn_list = [i for i in issues if i.severity == "warning"]
    out.append("## Advertencias del lint\n")
    if warn_list:
        for issue in sorted(warn_list, key=lambda i: (i.file, i.activity or "", i.code)):
            where = f"`{issue.file}`" + (f" `{issue.activity}`" if issue.activity else "")
            out.append(f"- {where}: {issue.code} — {issue.message}")
    else:
        out.append("Ninguna.")
    out.append("")
    return "\n".join(out)
