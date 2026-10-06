"""Paquete de revisión de una unidad o de un formulario de ruta (MVP-03 REQ-08, contrato §12).

Uso (desde apps/backend; `make review-packet UNIT=u1` hace lo mismo):
  uv run python ../../scripts/content/review_packet.py --unit u1
  uv run python ../../scripts/content/review_packet.py --unit inicial
  uv run python ../../scripts/content/review_packet.py --all     # regenera los existentes

Escribe `docs/contenido/revision/<unidad>.md` con los ítems y objetivos, las claves y
variantes, las fuentes por afirmación, las advertencias del lint, los guiones de audio y la
lista de revisión del contrato §12. Es determinista (sin fechas): la CI lo regenera con
`--all` y falla si hay diferencias. No toca la base de datos ni cambia estados editoriales.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "backend"))

from app.modules.content.lint import lint_dir, unit_number, word_count  # noqa: E402
from app.modules.content.loader import ContentBundle, Issue, LoadedItem  # noqa: E402
from app.modules.content.schema import (  # noqa: E402
    Activity,
    AssessmentFormFile,
    ChoiceActivity,
    GuidedDialogueActivity,
    LessonFile,
    Passage,
    RecordedSpeakingActivity,
    ScenarioFile,
    SentenceOrderActivity,
    ShortWritingActivity,
    WordCompletionActivity,
    content_hash,
    item_payload,
)

CONTENT = ROOT / "content"
OUT_DIR = ROOT / "docs" / "contenido" / "revision"
PATH_CODE = "toefl-ibt-2026-b1-b2"
FORMS = {"inicial": "initial", "final": "final"}
UNIT = re.compile(r"^u[1-8]$")

Model = LessonFile | ScenarioFile | AssessmentFormFile

CHECKLIST = (
    "El objetivo es observable y coincide con el mapa.",
    "La explicación es correcta y cada regla tiene fuente y alcance.",
    "Los ejemplos son originales y no ambiguos.",
    "Las claves están verificadas y las variantes válidas, listadas.",
    "Los distractores son plausibles y no hay dos respuestas defendibles.",
    "El apoyo en español aparece solo donde se permite.",
    "El audio coincide con el guion y se entiende.",
    "Hay alternativas de accesibilidad (transcripción, texto alternativo).",
    "No hay marcadores pendientes y el lint está limpio.",
)
KIND_ES = {"lesson": "lección", "scenario": "escenario", "assessment_form": "comprobación"}
FORM_ES = {"initial": "diagnóstico inicial", "checkpoint": "checkpoint", "final": "final"}


def select(bundle: ContentBundle, which: str) -> list[tuple[LoadedItem, Model]]:
    """Los ítems de una unidad (`u1`) o un formulario de ruta (`inicial`, `final`)."""
    chosen: list[tuple[LoadedItem, Model]] = []
    for loaded in bundle.items:
        model = loaded.model
        if model is None:
            continue
        if which in FORMS:
            if isinstance(model, AssessmentFormFile) and model.form_kind == FORMS[which]:
                chosen.append((loaded, model))
        elif (model.unit or "").startswith(f"{which}-"):
            chosen.append((loaded, model))
    return sorted(chosen, key=lambda pair: (pair[1].position, pair[1].slug))


def heading(bundle: ContentBundle, which: str) -> str:
    if which in FORMS:
        return f"Formulario de ruta: {FORM_ES[FORMS[which]]}"
    units = bundle.path.units if bundle.path else []
    for unit in units:
        if unit_number(unit.slug) == int(which[1:]):
            return f"Unidad {which[1:]} · {unit.title}"
    return f"Unidad {which[1:]}"


def cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


def audio_ids(model: Model) -> list[str]:
    ids: list[str] = []
    for act in model.activities:
        if act.stimulus is not None and act.stimulus.audio:
            ids.append(act.stimulus.audio)
        if isinstance(act, RecordedSpeakingActivity) and act.audio:
            ids.append(act.audio)
    return list(dict.fromkeys(ids))


def source_rows(bundle: ContentBundle, models: Iterable[Model]) -> list[str]:
    used: dict[str, list[str]] = {}
    for model in models:
        refs = [c.source for c in model.sources]
        if isinstance(model, LessonFile):
            refs += [r.source for r in model.pcre.rules if r.source]
        for act in model.activities:
            refs += act.sources
        for ref in refs:
            used.setdefault(ref, [])
            if model.slug not in used[ref]:
                used[ref].append(model.slug)
    known = {s.id: s for s in (bundle.sources.sources if bundle.sources else [])}
    rows = ["| Fuente | Editor | Estado | Consultada | Usada en |", "|---|---|---|---|---|"]
    for ref in sorted(used):
        src = known.get(ref)
        if src is None:
            rows.append(f"| `{ref}` | — | **no registrada** | — | {', '.join(used[ref])} |")
            continue
        state = "consultada" if src.status == "consulted" else "**pendiente**"
        rows.append(
            f"| [{cell(src.title)}]({src.url}) (`{ref}`) | {cell(src.publisher)} | {state} "
            f"| {src.accessed_on or '—'} | {', '.join(used[ref])} |"
        )
    return rows


def source_state(bundle: ContentBundle, ref: str | None) -> str:
    if not ref:
        return "sin fuente"
    for src in bundle.sources.sources if bundle.sources else []:
        if src.id == ref:
            return f"`{ref}` ({'consultada' if src.status == 'consulted' else 'pendiente'})"
    return f"`{ref}` (no registrada)"


def answer_lines(act: Activity) -> list[str]:
    """Clave, variantes y distractores de una actividad, según su formato."""
    if isinstance(act, ChoiceActivity):
        lines = []
        for opt in act.options:
            mark = "✔ clave" if opt.id in act.correct else "distractor"
            why = f" — {cell(opt.why_es)}" if opt.why_es else ""
            lines.append(f"  - `{opt.id}` ({mark}): {cell(opt.text)}{why}")
        return lines
    if isinstance(act, WordCompletionActivity):
        lines = [f"  - Texto: {cell(act.text_en)}"]
        for gap in act.gaps:
            case = ", distingue mayúsculas" if gap.case_sensitive else ""
            accepted = " · ".join(f"`{a}`" for a in gap.accepted)
            lines.append(f"  - `{gap.id}` (se ve «{gap.shown}»{case}): {accepted}")
        return lines
    if isinstance(act, SentenceOrderActivity):
        return [
            f"  - Orden aceptado {n}: {' / '.join(order)}"
            for n, order in enumerate(act.accepted_orders, start=1)
        ]
    if isinstance(act, ShortWritingActivity):
        return [
            f"  - {act.min_words}–{act.max_words} palabras · rúbrica `{act.rubric}` · "
            f"respuesta modelo de {word_count(act.model_answer)} palabras",
            f"  - Modelo: {cell(act.model_answer)}",
            f"  - Comentario: {cell(act.model_commentary_es)}",
        ]
    if isinstance(act, RecordedSpeakingActivity):
        if act.subtype == "listen_and_repeat":
            first = f"  - Repetir: «{act.target_sentence}» (audio `{act.audio}`)"
        else:
            first = (
                f"  - Pregunta: {cell(act.question_en or '')} "
                f"(preparación {act.prep_seconds} s, respuesta {act.response_seconds} s)"
            )
        return [
            first,
            f"  - Rúbrica `{act.rubric}` · modelo: {cell(act.model_answer)}",
            f"  - Comentario: {cell(act.model_commentary_es)}",
        ]
    if isinstance(act, GuidedDialogueActivity):
        lines = [f"  - Inicio `{act.start}`; caminos exitosos:"]
        lines += [f"    - {' → '.join(path)}" for path in act.success_paths]
        for node in act.nodes:
            lines.append(f"  - `{node.id}` ({node.speaker}): {cell(node.text_en)}")
            for move in node.options:
                tag = "" if move.good else ", mejorable"
                lines.append(
                    f"    - `{move.id}` (→ {move.next or 'fin'}{tag}): {cell(move.text)} "
                    f"— {cell(move.feedback_es)}"
                )
        return lines
    return []


def activity_block(act: Activity) -> list[str]:
    lines = [
        f"- **`{act.key}`** · {act.format} · `{act.task_family}` · pool `{act.pool}` · "
        f"{', '.join(act.objectives)}"
    ]
    if act.prompt_en:
        lines.append(f"  - Consigna: {cell(act.prompt_en)}")
    if act.stimulus is not None and act.stimulus.text_en:
        lines.append(f"  - Estímulo: {cell(act.stimulus.text_en)}")
    lines += answer_lines(act)
    extras = []
    if act.hints:
        extras.append(f"{len(act.hints)} pista(s)")
    if act.support_es:
        extras.append("apoyo en español")
    if act.stimulus is not None and act.stimulus.transcript:
        extras.append("transcripción")
    if act.example:
        extras.append("ejemplo")
    if extras:
        lines.append(f"  - Ayudas: {', '.join(extras)}")
    if act.explanation_es:
        lines.append(f"  - Explicación: {cell(act.explanation_es)}")
    return lines


def passage_lines(passages: list[Passage]) -> list[str]:
    lines: list[str] = []
    for p in passages:
        title = f" — {p.title_en}" if p.title_en else ""
        lines += ["", f"**Pasaje `{p.id}`{title}** ({word_count(p.text_en)} palabras)", ""]
        lines += [f"> {para}" if para else ">" for para in p.text_en.strip().splitlines()]
    return lines


def item_section(
    bundle: ContentBundle, loaded: LoadedItem, model: Model, issues: list[Issue]
) -> list[str]:
    objectives = {o.code: o for o in (bundle.objectives.objectives if bundle.objectives else [])}
    digest = content_hash(item_payload(model))
    kind = KIND_ES[model.kind]
    if isinstance(model, AssessmentFormFile):
        kind = f"{kind} ({FORM_ES[model.form_kind]}, {model.duration_minutes} min)"
    lines = [
        "",
        f"## {model.position}. {model.title}",
        "",
        f"- Archivo: `content/{loaded.file}` · {kind} · estado `{model.status}`",
        f"- Hash del contenido: `{digest[:12]}…` (el panel lo muestra en «Aprobar el hash»)",
        "- Objetivos:",
    ]
    for code in model.objectives:
        obj = objectives.get(code)
        lines.append(f"  - `{code}`: {cell(obj.description_es) if obj else '**no registrado**'}")
    if isinstance(model, LessonFile):
        lines += [
            f"- Objetivo observable: {cell(model.objective_es)}",
            "- PCRE:",
            f"  - Patrón: {cell(model.pcre.pattern)}",
            f"  - Concepto: {cell(model.pcre.concept)}",
        ]
        for n, rule in enumerate(model.pcre.rules, start=1):
            state = source_state(bundle, rule.source)
            lines.append(f"  - Regla {n} · fuente {state}: {cell(rule.text)}")
            if rule.applies_when_not_es:
                lines.append(f"    - Cuándo no aplica: {cell(rule.applies_when_not_es)}")
        lines += [f"  - Ejemplo: {cell(ex)}" for ex in model.pcre.examples]
        lines.append(f"- Tarea de aplicación: {cell(model.application_task_es)}")
    if isinstance(model, ScenarioFile):
        lines += [
            f"- Situación: {cell(model.situation_es)}",
            f"- Persona del agente: {cell(model.agent_persona_en)}",
            f"- Apertura: {cell(model.opening_en)} · máximo {model.max_seconds} s · "
            f"rúbrica `{model.rubric}`",
            f"- Movimientos requeridos: {'; '.join(model.required_moves)}",
        ]
    lines.append("- Afirmaciones y fuentes:")
    for claim in model.sources:
        lines.append(
            f"  - {cell(claim.claim)} — {source_state(bundle, claim.source)}, "
            f"alcance: {cell(claim.scope)}"
        )
    if isinstance(model, LessonFile | AssessmentFormFile):
        lines += passage_lines(model.passages)
    lines += ["", f"### Actividades ({len(model.activities)})", ""]
    for act in model.activities:
        lines += activity_block(act)
    own = [i for i in issues if i.file == loaded.file]
    lines += ["", "### Lint", ""]
    if own:
        for issue in sorted(own, key=lambda i: (i.severity != "error", i.code, i.activity or "")):
            where = f" [{issue.activity}]" if issue.activity else ""
            lines.append(f"- {issue.severity} `{issue.code}`{where}: {cell(issue.message)}")
    else:
        lines.append("- Sin errores ni advertencias.")
    ids = audio_ids(model)
    if ids:
        lines += ["", "### Guiones de audio", ""]
        entries = {e.id: e for e in bundle.audio.audio}
        for audio_id in ids:
            entry = entries.get(audio_id)
            if entry is None:
                lines.append(f"- `{audio_id}`: **sin entrada en el manifiesto**")
                continue
            state = f"revisado por {entry.reviewed_by}" if entry.reviewed_by else "sin revisar"
            file = f"`{entry.file}`" if entry.file else "sin MP3 (se genera en G2)"
            lines.append(f"- `{audio_id}` · {file} · {state}")
            lines += [f"  - {line.speaker}: {cell(line.text)}" for line in entry.script]
    lines += ["", "### Lista de revisión (contrato §12)", ""]
    lines += [f"- [ ] {n}. {text}" for n, text in enumerate(CHECKLIST, start=1)]
    return lines


def render(which: str) -> str:
    results = lint_dir(CONTENT)
    if PATH_CODE not in results:
        raise SystemExit(f"error: no existe la ruta {PATH_CODE} en {CONTENT}")
    bundle, issues = results[PATH_CODE]
    chosen = select(bundle, which)
    if not chosen:
        raise SystemExit(f"error: no hay ítems para {which}")
    files = {loaded.file for loaded, _ in chosen}
    own = [i for i in issues if i.file in files]
    errors = sum(1 for i in own if i.severity == "error")
    entries = {e.id: e for e in bundle.audio.audio}
    used_audio = sorted({a for _, m in chosen for a in audio_ids(m)})
    reviewed = sum(1 for a in used_audio if a in entries and entries[a].reviewed_by)
    lines = [
        f"# Paquete de revisión — {heading(bundle, which)}",
        "",
        f"> Generado por `make review-packet UNIT={which}` (MVP-03 REQ-08, contrato §12). No se",
        "> edita a mano: la CI lo regenera y falla si hay diferencias. Ruta "
        f"`{PATH_CODE}`, catálogo v{bundle.path.catalog_version if bundle.path else '?'}.",
        "",
        "## Cómo usarlo",
        "",
        "1. Revisa cada ítem con su lista (§12) junto al panel `/admin/contenido`, que muestra",
        "   la vista de alumno y la de autor.",
        "2. El hash de cada ítem es el que el panel muestra en «Aprobar el hash …». Si no",
        "   coincide, el archivo cambió después de este paquete: regenéralo.",
        "3. Registra los hallazgos en el panel; el agente los corrige en una revisión nueva.",
        "4. Una fuente **pendiente** no se pudo consultar: confírmala (y la regla que la cita)",
        "   o pide otra. El audio sin revisar bloquea aprobar y publicar hasta G2.",
        "",
        "## Resumen",
        "",
        "| # | Ítem | Tipo | Estado | Objetivos | Actividades | Hash |",
        "|---|---|---|---|---|---|---|",
    ]
    for _, model in chosen:
        lines.append(
            f"| {model.position} | {cell(model.title)} (`{model.slug}`) | {KIND_ES[model.kind]} "
            f"| `{model.status}` | {', '.join(model.objectives)} | {len(model.activities)} "
            f"| `{content_hash(item_payload(model))[:12]}` |"
        )
    lines += [
        "",
        f"- Lint de estos archivos: {errors} errores, {len(own) - errors} advertencias.",
        f"- Audio: {len(used_audio)} guiones, {reviewed} revisados, "
        f"{len(used_audio) - reviewed} sin revisar.",
        "",
        "## Fuentes citadas",
        "",
    ]
    lines += source_rows(bundle, (m for _, m in chosen))
    for loaded, model in chosen:
        lines += item_section(bundle, loaded, model, issues)
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--unit", help="u1 … u8, inicial o final")
    group.add_argument("--all", action="store_true", help="regenera los paquetes existentes")
    args = parser.parse_args(argv)
    if args.all:
        targets = sorted(p.stem for p in OUT_DIR.glob("*.md"))
    else:
        if not (UNIT.match(args.unit) or args.unit in FORMS):
            print("error: --unit acepta u1 … u8, inicial o final", file=sys.stderr)
            return 2
        targets = [args.unit]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for which in targets:
        out = OUT_DIR / f"{which}.md"
        out.write_text(render(which), encoding="utf-8")
        print(f"paquete escrito en {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
