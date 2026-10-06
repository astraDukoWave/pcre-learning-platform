"""AC-08: ningún DTO de alumno incluye soluciones, explicaciones, variantes aceptadas,
pistas ni rúbricas privadas antes de enviar.

La prueba publica la ruta de prueba completa y recorre las respuestas de todos los
endpoints de alumno registrados en `STUDENT_DTO_ENDPOINTS`. Cada change set que agrega un
endpoint de alumno lo registra aquí (en `student_endpoints`).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.helpers import Account

FORBIDDEN_KEYS = frozenset(
    {
        "solution",
        "correct",
        "accepted",
        "accepted_orders",
        "explanation",
        "explanation_es",
        "rubric",
        "hints",
        "support_es",
        "transcript",
        "example",
        "model_answer",
        "model_commentary_es",
        "why",
        "why_es",
        "feedback_es",
        "success_paths",
        "target_sentence",
        "good",
        "case_sensitive",
        "coach_hints",
        "agent_persona_en",
    }
)

# Fragmentos privados del contenido de prueba que nunca deben viajar como valor.
FORBIDDEN_VALUES = (
    "Busca los días de cada curso.",  # pista
    "Compara los horarios con el de Marta.",  # apoyo en español
    "Marta puede estudiar entre semana por la noche.",  # explicación
    "Es en sábado.",  # motivo de opción
    "Pregunta directa y clara.",  # feedback de diálogo
    "Dear Ms. Lee",  # respuesta modelo
)


def walk_keys(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, inner in value.items():
            yield str(key)
            yield from walk_keys(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from walk_keys(inner)


@pytest.fixture
def published(admin: Account, imported: Path) -> dict[str, str]:
    ids = {}
    for rev in admin.client.get("/api/v1/admin/content/revisions").json():
        admin.client.post(
            f"/api/v1/admin/content/revisions/{rev['id']}/approve",
            json={"content_hash": rev["content_hash"]},
            headers=admin.headers(),
        )
        res = admin.client.post(
            f"/api/v1/admin/content/revisions/{rev['id']}/publish", json={}, headers=admin.headers()
        )
        assert res.status_code == 200, res.text
        ids[rev["item_slug"]] = rev["item_id"]
    return ids


def student_endpoints(student: Account, ids: dict[str, str]) -> list[str]:
    paths = student.client.get("/api/v1/learning-paths").json()
    assert paths, "la ruta publicada debe aparecer"
    return [
        "/api/v1/learning-paths",
        f"/api/v1/learning-paths/{paths[0]['id']}",
        f"/api/v1/lessons/{ids['u1-l1-lectura']}",
        f"/api/v1/lessons/{ids['u1-l3-escritura']}",
        f"/api/v1/scenarios/{ids['u1-escenario']}",
    ]


def test_student_dtos_have_no_forbidden_keys(student: Account, published: dict[str, str]) -> None:
    for url in student_endpoints(student, published):
        res = student.client.get(url)
        assert res.status_code == 200, url
        leaked = set(walk_keys(res.json())) & FORBIDDEN_KEYS
        assert not leaked, f"{url} filtra {sorted(leaked)}"
        for fragment in FORBIDDEN_VALUES:
            assert fragment not in res.text, f"{url} filtra '{fragment}'"


def test_lesson_announces_aids_without_content(student: Account, published: dict[str, str]) -> None:
    lesson = student.client.get(f"/api/v1/lessons/{published['u1-l1-lectura']}").json()
    first = lesson["activities"][0]
    assert {"kind": "hint", "count": 1} in first["aids"]
    assert {"kind": "support_es", "count": 1} in first["aids"]
    assert all(a["pool"] == "practice" for a in lesson["activities"])  # el pool review no viaja
    assert lesson["pcre"]["examples"]


def test_unpublished_items_are_404(student: Account, imported: Path, admin: Account) -> None:
    rev = admin.client.get("/api/v1/admin/content/revisions").json()[0]
    assert student.client.get(f"/api/v1/lessons/{rev['item_id']}").status_code == 404
    assert student.client.get("/api/v1/learning-paths").json() == []
