"""Reglas puras del flujo editorial (`docs/arquitectura.md` §5.1, contrato §12).

`draft` → `approved` (por hash, humano) → `published`; la publicada anterior pasa a
`superseded`. `withdrawn` retira sin borrar historial. Una revisión aprobada o publicada
es inmutable: editar el archivo crea otra revisión `draft`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

STATUSES = ("draft", "approved", "published", "superseded", "withdrawn")
FINDING_SEVERITIES = ("material", "minor")
FINDING_STATUSES = ("open", "resolved", "wont_fix")
REPORT_CATEGORIES = ("answer_key", "unclear", "audio", "typo", "other")
REPORT_STATUSES = ("open", "triaged", "resolved", "wont_fix")

BLOCKER_MESSAGES = {
    "not_draft": "Solo se aprueba una revisión en borrador.",
    "not_approved": "Solo se publica una revisión aprobada.",
    "hash_mismatch": "El contenido cambió desde que lo revisaste (hash distinto).",
    "open_material_findings": "Hay hallazgos materiales abiertos.",
    "lint_errors": "El lint tiene errores.",
    "audio_pending": "Hay audio sin revisar.",
    "not_withdrawable": "Solo se retira una revisión aprobada o publicada.",
    "reason_required": "Escribe el motivo del retiro.",
}


@dataclass(frozen=True)
class RevisionFacts:
    status: str
    content_hash: str
    approved_hash: str | None
    open_material_findings: int
    lint_errors: int
    audio_pending: bool


def _quality_blockers(facts: RevisionFacts) -> list[str]:
    blockers = []
    if facts.open_material_findings > 0:
        blockers.append("open_material_findings")
    if facts.lint_errors > 0:
        blockers.append("lint_errors")
    if facts.audio_pending:
        blockers.append("audio_pending")
    return blockers


def approval_blockers(facts: RevisionFacts, reviewed_hash: str) -> list[str]:
    """Aprobar exige el hash que el revisor vio, cero hallazgos materiales abiertos, cero
    errores de lint y audio revisado (EDGE-13)."""
    blockers = [] if facts.status == "draft" else ["not_draft"]
    if reviewed_hash != facts.content_hash:
        blockers.append("hash_mismatch")
    return blockers + _quality_blockers(facts)


def publish_blockers(facts: RevisionFacts) -> list[str]:
    blockers = [] if facts.status == "approved" else ["not_approved"]
    if facts.status == "approved" and facts.approved_hash != facts.content_hash:
        blockers.append("hash_mismatch")
    return blockers + _quality_blockers(facts)


def withdraw_blockers(status: str, reason: str) -> list[str]:
    blockers = [] if status in ("approved", "published") else ["not_withdrawable"]
    if not reason.strip():
        blockers.append("reason_required")
    return blockers


def describe(blockers: list[str]) -> str:
    return " ".join(BLOCKER_MESSAGES[b] for b in blockers)


def shuffled_tokens(key: str, tokens: list[str]) -> list[str]:
    """Orden de fichas determinista y distinto del canónico (el orden no delata la clave)."""
    order = sorted(
        range(len(tokens)),
        key=lambda i: hashlib.sha256(f"{key}:{i}:{tokens[i]}".encode()).hexdigest(),
    )
    result = [tokens[i] for i in order]
    if result == tokens and len(tokens) > 1:
        result = result[1:] + result[:1]
    return result
