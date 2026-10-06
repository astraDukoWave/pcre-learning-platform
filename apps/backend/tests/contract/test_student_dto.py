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
        "next_review",
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
    "Attention please.",  # transcripción de la escucha
    "travelling-variante-secreta",  # variante aceptada
    "I would like a table for two",  # oración objetivo de la repetición
    "Respuesta modelo secreta",  # respuesta modelo de la entrevista
    "Comentario secreto",  # comentario del ejemplo
    "Usually va antes del verbo",  # explicación del orden
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
def published(all_formats: dict[str, Any]) -> dict[str, str]:
    """Ruta de prueba con los seis formatos, aprobada y publicada completa."""
    return {slug: v["item_id"] for slug, v in all_formats.items()}


def student_endpoints(student: Account, ids: dict[str, str]) -> list[str]:
    paths = student.client.get("/api/v1/learning-paths").json()
    assert paths, "la ruta publicada debe aparecer"
    return [
        "/api/v1/me",
        "/api/v1/me/export",
        "/api/v1/learning-paths",
        f"/api/v1/learning-paths/{paths[0]['id']}",
        f"/api/v1/lessons/{ids['u1-l1-lectura']}",
        f"/api/v1/lessons/{ids['u1-l2-escucha']}",
        f"/api/v1/lessons/{ids['u1-l3-escritura']}",
        f"/api/v1/lessons/{ids['u1-l4-habla']}",
        f"/api/v1/scenarios/{ids['u1-escenario']}",
    ]


def test_student_dtos_have_no_forbidden_keys(student: Account, published: dict[str, str]) -> None:
    formats = set()
    for url in student_endpoints(student, published):
        if "/lessons/" in url or "/scenarios/" in url:
            formats |= {a["format"] for a in student.client.get(url).json()["activities"]}
        res = student.client.get(url)
        assert res.status_code == 200, url
        leaked = set(walk_keys(res.json())) & FORBIDDEN_KEYS
        assert not leaked, f"{url} filtra {sorted(leaked)}"
        for fragment in FORBIDDEN_VALUES:
            assert fragment not in res.text, f"{url} filtra '{fragment}'"
    assert formats == {
        "choice",
        "word_completion",
        "sentence_order",
        "short_writing",
        "recorded_speaking",
        "guided_dialogue",
    }


def test_lesson_announces_aids_without_content(student: Account, published: dict[str, str]) -> None:
    lesson = student.client.get(f"/api/v1/lessons/{published['u1-l1-lectura']}").json()
    first = lesson["activities"][0]
    assert {"kind": "hint", "count": 1} in first["aids"]
    assert {"kind": "support_es", "count": 1} in first["aids"]
    assert all(a["pool"] == "practice" for a in lesson["activities"])  # el pool review no viaja
    assert lesson["pcre"]["examples"]


def test_tokens_are_shuffled(student: Account, published: dict[str, str]) -> None:
    lesson = student.client.get(f"/api/v1/lessons/{published['u1-l3-escritura']}").json()
    order = next(a for a in lesson["activities"] if a["format"] == "sentence_order")
    assert order["data"]["tokens"] != ["I", "usually", "walk", "to work"]


def test_unpublished_items_are_404(student: Account, imported: Path, admin: Account) -> None:
    rev = admin.client.get("/api/v1/admin/content/revisions").json()[0]
    assert student.client.get(f"/api/v1/lessons/{rev['item_id']}").status_code == 404
    assert student.client.get("/api/v1/learning-paths").json() == []
