"""AC-08: ningún DTO de alumno incluye soluciones, explicaciones, variantes aceptadas,
pistas ni rúbricas privadas antes de enviar.

La prueba publica la ruta de prueba completa y recorre las respuestas de todos los
endpoints de alumno registrados en `STUDENT_DTO_ENDPOINTS`. Cada change set que agrega un
endpoint de alumno lo registra aquí (en `student_endpoints`).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.core.clock import FakeClock
from app.core.config import REPO_DIR
from app.modules.content.domain import shuffled_options
from tests.helpers import Account, start

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


def no_leak(res: Any, where: str, *, keys: bool = True) -> None:
    assert res.status_code == 200, (where, res.text)
    if keys:
        leaked = set(walk_keys(res.json())) & FORBIDDEN_KEYS
        assert not leaked, f"{where} filtra {sorted(leaked)}"
    for fragment in FORBIDDEN_VALUES:
        assert fragment not in res.text, f"{where} filtra '{fragment}'"


def test_review_and_progress_dtos_do_not_leak(
    student: Account, all_formats: dict[str, Any], clock: FakeClock
) -> None:
    """Hallazgo 2 del verificador de CS-12: repasos (reparación y vencidos) y progreso. En
    `/me/progress` las claves `hint`, `example` y `correct` son conteos: se revisan valores."""
    act = all_formats["u1-l1-lectura"]["activities"]["u1.l1.p1"]
    res = student.client.post(
        "/api/v1/attempts",
        json={"activity_id": act, "response": {"selected": ["b"]}},
        headers={**student.headers(), "Idempotency-Key": str(uuid.uuid4())},
    )
    assert res.status_code == 201
    repair = student.client.get("/api/v1/me/reviews/next", params={"objective": "U1.R"})
    assert repair.json()["review"] is not None
    no_leak(repair, "/me/reviews/next?objective")
    clock.advance(timedelta(hours=25))
    student.relogin()
    due = student.client.get("/api/v1/me/reviews/next")
    assert due.json()["review"]["due"] is True
    no_leak(due, "/me/reviews/next")
    no_leak(student.client.get("/api/v1/me/progress"), "/me/progress", keys=False)
    no_leak(student.client.get("/api/v1/me/reviews"), "/me/reviews", keys=False)


def test_assessment_dtos_do_not_leak(student: Account, forms: dict[str, Any]) -> None:
    form = forms["u1-checkpoint"]
    run = start(student, form["id"]).json()
    no_leak(student.client.get(f"/api/v1/assessments/{form['id']}"), "/assessments/{id}")
    no_leak(student.client.get(f"/api/v1/assessment-runs/{run['id']}"), "/assessment-runs/{id}")


def test_shuffled_options_is_a_stable_permutation() -> None:
    items = ["a", "b", "c", "d"]
    once = shuffled_options("u1.l1.p1", items)
    assert sorted(once) == items and once == shuffled_options("u1.l1.p1", items)
    orders = {tuple(shuffled_options(f"k{i}", items)) for i in range(20)}
    assert len(orders) > 5  # varía entre actividades


def test_real_content_keys_are_not_in_a_fixed_position(
    admin: Account, student: Account, editorial: Any
) -> None:
    """Hallazgo 1 del verificador de CS-12: en el contenido real la clave de selección no
    está siempre en la misma letra ni en la misma posición de lo que recibe el alumno."""
    letters = [
        tuple(act["correct"])
        for path in sorted((REPO_DIR / "content" / "toefl-ibt-2026-b1-b2").rglob("*.yaml"))
        for act in (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("activities", [])
        if isinstance(act, dict) and act.get("format") == "choice"
    ]
    assert len(letters) >= 20 and len(set(letters)) >= 3
    editorial.import_dir(REPO_DIR / "content")
    rev = next(
        r
        for r in admin.client.get("/api/v1/admin/content/revisions").json()
        if r["item_slug"] == "u1-l1-lectura"
    )
    admin.client.post(
        f"/api/v1/admin/content/revisions/{rev['id']}/approve",
        json={"content_hash": rev["content_hash"]},
        headers=admin.headers(),
    )
    detail = admin.client.post(
        f"/api/v1/admin/content/revisions/{rev['id']}/publish", json={}, headers=admin.headers()
    ).json()
    solutions = {
        a["key"]: a["solution"]["correct"] for a in detail["activities"] if a["format"] == "choice"
    }
    lesson = student.client.get(f"/api/v1/lessons/{rev['item_id']}").json()
    positions = [
        [o["id"] for o in act["data"]["options"]].index(solutions[act["key"]][0])
        for act in lesson["activities"]
        if act["format"] == "choice"
    ]
    assert len(positions) >= 4 and len(set(positions)) >= 2, positions
