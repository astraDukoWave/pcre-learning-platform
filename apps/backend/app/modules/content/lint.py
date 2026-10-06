"""Lint del contenido (REQ-07). Errores bloquean la CI y la importación; advertencias se
muestran en el panel y `pending_audio` bloquea aprobar y publicar.

Errores: esquema; claves únicas en toda la ruta; referencias (objetivos, fuentes,
rúbricas, audio, pasajes); familia ↔ formato; pools disjuntos; mínimos del contrato §5;
marcadores prohibidos; apoyo en español solo en práctica de U1–U4; ayudas en comprobación.
Advertencias: reglas absolutas; extensiones fuera de rango; audio sin revisar; reglas sin
fuente; fuentes pendientes.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from app.modules.content.loader import ContentBundle, Issue
from app.modules.content.schema import (
    CLOSED_FORMATS,
    FAMILY_FORMATS,
    LISTENING_FAMILIES,
    PRODUCTION_FORMATS,
    AssessmentFormFile,
    ChoiceActivity,
    LessonFile,
    RecordedSpeakingActivity,
    ScenarioFile,
    ShortWritingActivity,
    WordCompletionActivity,
    script_hash,
)

MARKERS = re.compile(r"\b(TODO|TBD|lorem|placeholder|XXX)\b", re.IGNORECASE)
ABSOLUTE = re.compile(r"\b(siempre|nunca|always|never|must)\b", re.IGNORECASE)
WORDS = re.compile(r"[A-Za-z0-9'’-]+")
WORDS_PER_SECOND = 2.5  # ~150 palabras por minuto (ritmo natural B1–B2)

READING_RANGES = {range(1, 4): (120, 250), range(4, 7): (120, 350), range(7, 9): (120, 450)}
ACADEMIC_RANGE = (300, 450)
LISTENING_SECONDS = {
    "listen_announcement": (20, 40),
    "listen_choose_response": (3, 20),
    "listen_conversation": (45, 90),
    "listen_academic_talk": (90, 150),
}

Item = LessonFile | ScenarioFile | AssessmentFormFile
Report = Callable[[str, str], None]


def unit_number(slug: str | None) -> int | None:
    if not slug:
        return None
    match = re.match(r"^u(\d+)-", slug)
    return int(match.group(1)) if match else None


def word_count(text: str) -> int:
    return len(WORDS.findall(text))


def audio_status(bundle: ContentBundle, audio_id: str) -> str:
    """`ready` (archivo presente y revisado), `pending` o `missing` (sin entrada)."""
    entry = next((a for a in bundle.audio.audio if a.id == audio_id), None)
    if entry is None:
        return "missing"
    if not entry.file or not entry.reviewed_by:
        return "pending"
    if not (bundle.path_dir / "audio" / entry.file).exists():
        return "pending"
    return "ready"


def lint_bundle(bundle: ContentBundle) -> list[Issue]:
    issues = list(bundle.issues)
    if bundle.path is None or bundle.objectives is None or bundle.sources is None:
        return issues
    issues += _lint_registries(bundle)
    seen_slugs: dict[str, str] = {}
    seen_keys: dict[str, str] = {}
    fingerprints: dict[str, tuple[str, str, str]] = {}
    for loaded in bundle.items:
        for marker in MARKERS.findall(loaded.raw_text):
            issues.append(
                Issue("error", "forbidden_marker", loaded.file, f"marcador prohibido: {marker}")
            )
        item = loaded.model
        if item is None:
            continue
        if item.slug in seen_slugs:
            issues.append(
                Issue(
                    "error",
                    "duplicate_slug",
                    loaded.file,
                    f"slug repetido con {seen_slugs[item.slug]}",
                )
            )
        seen_slugs[item.slug] = loaded.file
        for act in item.activities:
            if act.key in seen_keys:
                issues.append(
                    Issue(
                        "error",
                        "duplicate_key",
                        loaded.file,
                        f"clave repetida con {seen_keys[act.key]}",
                        act.key,
                    )
                )
            seen_keys[act.key] = loaded.file
            fp = _fingerprint(item, act)
            if fp:
                fingerprints.setdefault(fp, (loaded.file, act.key, act.pool))
                first = fingerprints[fp]
                if (first[2] == "assessment") != (act.pool == "assessment"):
                    issues.append(
                        Issue(
                            "error",
                            "pool_overlap",
                            loaded.file,
                            f"mismo ítem que {first[1]} ({first[0]}) en otro pool",
                            act.key,
                        )
                    )
        issues += _lint_item(bundle, loaded.file, item)
    return issues


def _fingerprint(item: Item, act: object) -> str | None:
    prompt = getattr(act, "prompt_en", "") or ""
    stim = getattr(act, "stimulus", None)
    stimulus = ""
    if stim is not None:
        if stim.text_en:
            stimulus = stim.text_en
        elif stim.passage:
            passages = {p.id: p.text_en for p in getattr(item, "passages", [])}
            stimulus = passages.get(stim.passage, stim.passage)
        elif stim.audio:
            stimulus = f"audio:{stim.audio}"
    options = ""
    if isinstance(act, ChoiceActivity):
        options = "|".join(o.text for o in act.options)
    if isinstance(act, WordCompletionActivity):
        options = act.text_en
    if not (prompt or stimulus or options):
        return None
    norm = re.sub(r"\s+", " ", f"{prompt}#{stimulus}#{options}".lower()).strip()
    return hashlib.sha256(norm.encode()).hexdigest()


def _lint_registries(bundle: ContentBundle) -> list[Issue]:
    issues: list[Issue] = []
    assert bundle.path and bundle.objectives and bundle.sources
    codes = [o.code for o in bundle.objectives.objectives]
    for code, n in Counter(codes).items():
        if n > 1:
            issues.append(
                Issue("error", "duplicate_objective", "objectives.yaml", f"{code} repetido")
            )
    ids = [s.id for s in bundle.sources.sources]
    for sid, n in Counter(ids).items():
        if n > 1:
            issues.append(Issue("error", "duplicate_source", "sources.yaml", f"{sid} repetida"))
    slugs = [u.slug for u in bundle.path.units]
    positions = [u.position for u in bundle.path.units]
    if len(set(slugs)) != len(slugs) or len(set(positions)) != len(positions):
        issues.append(
            Issue("error", "duplicate_unit", "path.yaml", "unidades con slug o posición repetidos")
        )
    manifest_dir = bundle.path_dir / "audio"
    for entry in bundle.audio.audio:
        rel = f"{bundle.rel(manifest_dir)}/manifest.yaml"
        if entry.file:
            file = manifest_dir / entry.file
            if not file.exists():
                issues.append(
                    Issue("error", "audio_missing", rel, f"{entry.id}: no existe {entry.file}")
                )
            elif entry.sha256 and hashlib.sha256(file.read_bytes()).hexdigest() != entry.sha256:
                issues.append(Issue("error", "audio_hash", rel, f"{entry.id}: sha256 distinto"))
            if entry.provider in (None, "fake", "fake-tts") or not entry.model:
                issues.append(
                    Issue(
                        "error", "audio_provider", rel, f"{entry.id}: el audio exige proveedor real"
                    )
                )
            if entry.script_hash and entry.script_hash != script_hash(entry):
                issues.append(
                    Issue(
                        "error",
                        "audio_script_changed",
                        rel,
                        f"{entry.id}: el guion cambió; regenera el audio",
                    )
                )
    return issues


def _lint_item(bundle: ContentBundle, file: str, item: Item) -> list[Issue]:
    assert bundle.path and bundle.objectives and bundle.sources
    issues: list[Issue] = []
    unit_slugs = {u.slug for u in bundle.path.units}
    objective_codes = {o.code for o in bundle.objectives.objectives}
    source_ids = {s.id: s for s in bundle.sources.sources}
    rubric_ids = {r.id for r in bundle.rubrics.rubrics} if bundle.rubrics else set()
    unit_slug = getattr(item, "unit", None)
    unit_n = unit_number(unit_slug)

    def err(code: str, message: str, activity: str | None = None) -> None:
        issues.append(Issue("error", code, file, message, activity))

    def warn(code: str, message: str, activity: str | None = None) -> None:
        issues.append(Issue("warning", code, file, message, activity))

    if unit_slug is not None and unit_slug not in unit_slugs:
        err("unknown_unit", f"la unidad {unit_slug} no está en path.yaml")
    for code in item.objectives:
        if code not in objective_codes:
            err("unknown_objective", f"objetivo inexistente: {code}")
    cited: set[str] = set()
    for claim in item.sources:
        cited.add(claim.source)
        if claim.source not in source_ids:
            err("unknown_source", f"fuente inexistente: {claim.source}")
        elif source_ids[claim.source].status == "pending":
            warn("source_pending", f"la fuente {claim.source} está pendiente de consultar")

    if isinstance(item, LessonFile):
        publishers = {source_ids[c].publisher for c in cited if c in source_ids}
        if "ETS" not in publishers:
            err("ets_source_required", "cada lección cita ETS para el formato")
        for rule in item.pcre.rules:
            if ABSOLUTE.search(rule.text):
                warn("absolute_rule", f"regla absoluta, confírmala: “{rule.text[:60]}”")
            if not rule.source:
                warn("rule_without_source", f"regla sin fuente: “{rule.text[:60]}”")
            elif rule.source not in source_ids:
                err("unknown_source", f"fuente inexistente en una regla: {rule.source}")
        _lesson_minimums(item, err)
        _passage_lengths(item, unit_n, warn)
    if isinstance(item, ScenarioFile):
        if item.rubric not in rubric_ids:
            err("unknown_rubric", f"rúbrica inexistente: {item.rubric}")
        dialogues = [a for a in item.activities if a.format == "guided_dialogue"]
        if len(dialogues) != 1:
            err("scenario_dialogue", "un escenario lleva exactamente un guided_dialogue")
    if isinstance(item, AssessmentFormFile):
        _form_minimums(item, err)

    passages = {p.id for p in getattr(item, "passages", [])}
    for act in item.activities:
        if act.format not in FAMILY_FORMATS[act.task_family]:
            err("family_format", f"{act.task_family} no usa el formato {act.format}", act.key)
        for code in act.objectives:
            if code not in objective_codes:
                err("unknown_objective", f"objetivo inexistente: {code}", act.key)
        for sid in act.sources:
            if sid not in source_ids:
                err("unknown_source", f"fuente inexistente: {sid}", act.key)
        is_form = isinstance(item, AssessmentFormFile)
        if is_form and act.pool != "assessment":
            err("pool_mismatch", "un formulario solo lleva ítems del pool assessment", act.key)
        if not is_form and act.pool == "assessment":
            err(
                "pool_mismatch",
                "el pool assessment solo va en formularios de comprobación",
                act.key,
            )
        if isinstance(item, ScenarioFile) and act.pool != "practice":
            err("pool_mismatch", "un escenario es práctica", act.key)
        if act.support_es and (act.pool != "practice" or unit_n is None or unit_n > 4):
            err("support_es_not_allowed", "apoyo en español solo en práctica de U1–U4", act.key)
        if is_form and (act.hints or act.support_es or act.example):
            err("aids_in_assessment", "una comprobación no muestra ayudas", act.key)
        stim = act.stimulus
        if stim is not None and stim.passage and stim.passage not in passages:
            err("unknown_passage", f"pasaje inexistente: {stim.passage}", act.key)
        audio_ids = []
        if stim is not None and stim.audio:
            audio_ids.append(stim.audio)
        if isinstance(act, RecordedSpeakingActivity) and act.audio:
            audio_ids.append(act.audio)
        for audio_id in audio_ids:
            status = audio_status(bundle, audio_id)
            if status == "missing":
                err("unknown_audio", f"audio sin entrada en el manifiesto: {audio_id}", act.key)
            elif status == "pending":
                warn(
                    "pending_audio",
                    f"audio sin revisar: {audio_id} (bloquea aprobar y publicar)",
                    act.key,
                )
        if act.task_family in LISTENING_FAMILIES and not (stim and stim.audio):
            err("listening_without_audio", "un ítem de escucha lleva audio y guion", act.key)
        if act.task_family in LISTENING_FAMILIES and stim and stim.audio:
            entry = next((a for a in bundle.audio.audio if a.id == stim.audio), None)
            if entry is not None and act.task_family in LISTENING_SECONDS:
                seconds = sum(word_count(line.text) for line in entry.script) / WORDS_PER_SECOND
                low, high = LISTENING_SECONDS[act.task_family]
                if not low <= seconds <= high:
                    warn(
                        "length_out_of_range",
                        f"duración estimada {seconds:.0f} s fuera de {low}–{high} s",
                        act.key,
                    )
        rubric = getattr(act, "rubric", None)
        if (
            isinstance(act, ShortWritingActivity | RecordedSpeakingActivity)
            and rubric not in rubric_ids
        ):
            err("unknown_rubric", f"rúbrica inexistente: {rubric}", act.key)
    return issues


def _lesson_minimums(item: LessonFile, report: Report) -> None:
    practice = [a for a in item.activities if a.pool == "practice"]
    review = [a for a in item.activities if a.pool == "review"]
    if item.skill in ("reading", "listening"):
        if len(practice) < 4 or len(review) < 4:
            report(
                "minimum_items",
                f"lectura y escucha: 4 ítems de práctica y 4 de repaso "
                f"(hay {len(practice)} y {len(review)})",
            )
    else:
        productions = [a for a in practice if a.format in PRODUCTION_FORMATS]
        prompts = {
            (getattr(a, "prompt_en", ""), getattr(a, "question_en", "")) for a in productions
        }
        if len(productions) < 2 or len(prompts) < 2:
            report(
                "minimum_items",
                f"escritura y habla: 2 consignas distintas de producción (hay {len(prompts)})",
            )


def _form_minimums(item: AssessmentFormFile, report: Report) -> None:
    closed = [a for a in item.activities if a.format in CLOSED_FORMATS]
    writing = [a for a in item.activities if a.format == "short_writing"]
    speaking = [a for a in item.activities if a.format == "recorded_speaking"]
    if item.form_kind == "checkpoint":
        if len(closed) < 6 or len(writing) + len(speaking) < 1:
            report(
                "minimum_items",
                f"checkpoint: 6 cerrados y una producción "
                f"(hay {len(closed)} y {len(writing) + len(speaking)})",
            )
    elif (len(closed), len(writing), len(speaking)) != (12, 2, 2):
        report(
            "minimum_items",
            f"formulario de ruta: 12 cerrados, 2 escritas y 2 orales "
            f"(hay {len(closed)}, {len(writing)} y {len(speaking)})",
        )


def _passage_lengths(item: LessonFile, unit_n: int | None, report: Report) -> None:
    if item.skill != "reading" or unit_n is None:
        return
    academic = any(a.task_family == "read_academic_passage" for a in item.activities)
    for passage in item.passages:
        words = word_count(passage.text_en)
        default = (120, 450)
        low, high = (
            ACADEMIC_RANGE
            if academic and unit_n >= 5
            else next((v for k, v in READING_RANGES.items() if unit_n in k), default)
        )
        if not low <= words <= high:
            report(
                "length_out_of_range", f"pasaje {passage.id}: {words} palabras (rango {low}–{high})"
            )


def summarize(issues: list[Issue]) -> tuple[int, int]:
    errors = sum(1 for i in issues if i.severity == "error")
    return errors, len(issues) - errors


def lint_dir(content_root: Path) -> dict[str, tuple[ContentBundle, list[Issue]]]:
    from app.modules.content.loader import discover_paths, load_path_dir

    out = {}
    for path_dir in discover_paths(content_root):
        bundle = load_path_dir(path_dir, content_root)
        out[path_dir.name] = (bundle, lint_bundle(bundle))
    return out
