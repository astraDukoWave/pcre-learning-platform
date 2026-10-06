"""REQ-12 (comprobaciones): orden fijado, respuestas guardadas sin feedback, envío
idempotente con resultados por objetivo, diagnóstico único con reinicio de admin (EDGE-09),
checkpoint numerado, "no evaluable (audio)" (EDGE-07), retomar la corrida (EDGE-17) y AC-08
en modo comprobación."""

from __future__ import annotations

import threading
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.bootstrap import Container
from app.main import create_app
from app.modules.content.service_editorial import EditorialService
from app.modules.identity.models import UserRole
from app.modules.practice.models import AssessmentRun, Attempt
from tests.content.builder import add_initial_form, write_content
from tests.contract.test_student_dto import FORBIDDEN_KEYS, walk_keys
from tests.helpers import Account, AccountFactory, create_user, login

LABEL = "Comprobación formativa: no es un examen oficial"


@pytest.fixture
def forms(admin: Account, editorial: object, tmp_path: Path) -> dict[str, Any]:
    """Ruta de prueba con el checkpoint de U1 y el diagnóstico inicial publicados."""
    editorial.import_dir(write_content(tmp_path / "forms", add_initial_form))  # type: ignore[attr-defined]
    ids: dict[str, Any] = {}
    for rev in admin.client.get("/api/v1/admin/content/revisions").json():
        if rev["item_slug"] not in ("u1-checkpoint", "diagnostico-inicial"):
            continue
        admin.client.post(
            f"/api/v1/admin/content/revisions/{rev['id']}/approve",
            json={"content_hash": rev["content_hash"]},
            headers=admin.headers(),
        )
        res = admin.client.post(
            f"/api/v1/admin/content/revisions/{rev['id']}/publish", json={}, headers=admin.headers()
        )
        assert res.status_code == 200, res.text
        ids[rev["item_slug"]] = {
            "id": rev["item_id"],
            "activities": {a["key"]: a["id"] for a in res.json()["activities"]},
        }
    return ids


def start(acct: Account, form_id: str, key: str | None = None) -> Any:
    return acct.client.post(
        f"/api/v1/assessments/{form_id}/start",
        headers={**acct.headers(), "Idempotency-Key": key or str(uuid.uuid4())},
    )


def save(acct: Account, run_id: str, activity_id: str, response: dict[str, Any], **kw: Any) -> Any:
    return acct.client.put(
        f"/api/v1/assessment-runs/{run_id}/answers/{activity_id}",
        json={"response": response, **kw},
        headers=acct.headers(),
    )


def submit(acct: Account, run_id: str, key: str | None = None) -> Any:
    return acct.client.post(
        f"/api/v1/assessment-runs/{run_id}/submit",
        headers={**acct.headers(), "Idempotency-Key": key or str(uuid.uuid4())},
    )


def test_start_fixes_order_and_hides_aids_and_solutions(
    student: Account, forms: dict[str, Any]
) -> None:
    form = forms["u1-checkpoint"]
    info = student.client.get(f"/api/v1/assessments/{form['id']}").json()
    assert info["can_start"] is True and info["runs"] == [] and info["label"] == LABEL
    res = start(student, form["id"])
    assert res.status_code == 201, res.text
    run = res.json()
    assert run["run_number"] == 1 and run["comparable"] is True and run["status"] == "in_progress"
    assert run["label"] == LABEL and run["form"]["form_kind"] == "checkpoint"
    keys = [f"u1.cp.a{i}" for i in range(1, 7)] + ["u1.cp.w1"]
    assert [i["id"] for i in run["items"]] == [form["activities"][k] for k in keys]
    assert all(i["aids"] == [] for i in run["items"])
    leaked = set(walk_keys(run)) & FORBIDDEN_KEYS
    assert not leaked, f"la corrida filtra {sorted(leaked)}"
    assert "Marta puede estudiar" not in res.text  # explicación de los ítems

    # Volver a iniciar retoma la misma corrida (EDGE-17); misma clave → misma respuesta.
    again = start(student, form["id"])
    assert again.status_code == 200 and again.json()["id"] == run["id"]
    key = str(uuid.uuid4())
    first, replay = start(student, form["id"], key), start(student, form["id"], key)
    assert replay.headers.get("Idempotent-Replayed") == "true"
    assert replay.json() == first.json()


def test_answers_are_saved_without_feedback_and_isolated(
    student: Account, forms: dict[str, Any], make_account: AccountFactory
) -> None:
    form = forms["u1-checkpoint"]
    run = start(student, form["id"]).json()
    a1 = form["activities"]["u1.cp.a1"]
    assert save(student, run["id"], a1, {"selected": ["z"]}).status_code == 422
    saved = save(student, run["id"], a1, {"selected": ["b"]})
    assert saved.status_code == 200
    assert set(saved.json()) == {"activity_id", "saved_at"}  # sin resultado
    save(student, run["id"], a1, {"selected": ["a"]})  # cambiar de opinión sobrescribe
    detail = student.client.get(f"/api/v1/assessment-runs/{run['id']}").json()
    assert detail["answers"][a1]["response"] == {"selected": ["a"]}
    assert detail["results"] == [] and detail["summary"] is None
    foreign = forms["diagnostico-inicial"]["activities"]["dx.c1"]
    assert save(student, run["id"], foreign, {"selected": ["a"]}).status_code == 404
    other = make_account("otra@example.com")
    assert other.client.get(f"/api/v1/assessment-runs/{run['id']}").status_code == 404
    assert save(other, run["id"], a1, {"selected": ["a"]}).status_code == 404
    assert submit(other, run["id"]).status_code == 404


def test_submit_grades_by_objective_and_is_idempotent(
    student: Account, forms: dict[str, Any], db: Session
) -> None:
    form = forms["u1-checkpoint"]
    acts = form["activities"]
    run = start(student, form["id"]).json()
    for i in range(1, 5):
        save(student, run["id"], acts[f"u1.cp.a{i}"], {"selected": ["a"]})
    save(student, run["id"], acts["u1.cp.a5"], {"selected": ["b"]})
    save(student, run["id"], acts["u1.cp.a6"], {}, audio_failed=True)  # EDGE-07
    save(
        student, run["id"], acts["u1.cp.w1"], {"text": "Dear Ms. Lee, could you tell me the hours?"}
    )
    key = str(uuid.uuid4())
    res = submit(student, run["id"], key)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "submitted"
    assert body["summary"] == {
        "objectives": [{"code": "U1.R", "correct": 4, "total": 5, "not_evaluable": 1}],
        "closed_correct": 4,
        "closed_total": 5,
        "productions_answered": 1,
        "productions_total": 1,
        "not_evaluable_audio": 1,
    }
    results = {r["activity_id"]: r for r in body["results"]}
    assert results[acts["u1.cp.a5"]]["correct"] is False
    assert results[acts["u1.cp.a5"]]["feedback"]["explanation"]  # explicaciones al enviar
    assert results[acts["u1.cp.a6"]]["evaluation_status"] == "not_evaluable"
    writing = results[acts["u1.cp.w1"]]
    assert writing["evaluation_status"] == "pending" and writing["feedback"]["model_answer"]
    assert writing["feedback"]["rubric"]  # autoevaluación opcional después de enviar

    # Idempotente: misma clave → misma respuesta; otra clave → mismos resultados y nada nuevo.
    assert submit(student, run["id"], key).json() == body
    assert submit(student, run["id"]).json()["summary"] == body["summary"]
    attempts = db.scalar(
        select(func.count()).select_from(Attempt).where(Attempt.assessment_run_id == run["id"])
    )
    assert attempts == 7
    assert save(student, run["id"], acts["u1.cp.a1"], {"selected": ["b"]}).status_code == 409

    # La autoevaluación de la producción es opcional y usa la ruta de siempre.
    assessed = student.client.post(
        f"/api/v1/attempts/{writing['attempt_id']}/self-assessment",
        json={"scores": {"task": 2}},
        headers=student.headers(),
    )
    assert assessed.status_code == 200 and assessed.json()["mode"] == "assessment"


def test_checkpoint_repeats_with_numbered_runs(student: Account, forms: dict[str, Any]) -> None:
    form = forms["u1-checkpoint"]
    first = start(student, form["id"]).json()
    submit(student, first["id"])
    second = start(student, form["id"])
    assert second.status_code == 201
    assert second.json()["run_number"] == 2 and second.json()["comparable"] is False
    info = student.client.get(f"/api/v1/assessments/{form['id']}").json()
    assert [r["run_number"] for r in info["runs"]] == [1, 2]
    assert info["open_run_id"] == second.json()["id"] and info["can_start"] is False


def test_diagnostic_runs_once_until_an_admin_resets_it(
    student: Account, admin: Account, forms: dict[str, Any], db: Session
) -> None:
    form = forms["diagnostico-inicial"]
    run = start(student, form["id"]).json()
    assert len(run["items"]) == 16
    submit(student, run["id"])
    again = start(student, form["id"])
    assert again.status_code == 409 and again.json()["error"]["code"] == "diagnostic_done"
    assert student.client.get(f"/api/v1/assessments/{form['id']}").json()["can_start"] is False

    url = f"/api/v1/admin/users/{student.id}/diagnostic-reset"
    assert student.client.post(url, headers=student.headers()).status_code == 403
    res = admin.client.post(url, headers=admin.headers())
    assert res.status_code == 200 and res.json() == {"reset": 1}
    assert admin.client.post(url, headers=admin.headers()).status_code == 404
    fresh = start(student, form["id"])
    assert fresh.status_code == 201 and fresh.json()["run_number"] == 2
    kept = db.scalars(select(AssessmentRun).where(AssessmentRun.id == run["id"])).one()
    assert kept.reset_at is not None and kept.summary is not None  # queda en el historial


def test_path_shows_form_state(student: Account, forms: dict[str, Any]) -> None:
    paths = student.client.get("/api/v1/learning-paths").json()
    detail = student.client.get(f"/api/v1/learning-paths/{paths[0]['id']}").json()
    diagnostic = next(f for f in detail["assessments"] if f["slug"] == "diagnostico-inicial")
    assert diagnostic["state"] == "not_started"
    start(student, forms["diagnostico-inicial"]["id"])
    detail = student.client.get(f"/api/v1/learning-paths/{paths[0]['id']}").json()
    diagnostic = next(f for f in detail["assessments"] if f["slug"] == "diagnostico-inicial")
    assert diagnostic["state"] == "in_progress"


def test_concurrent_starts_create_one_run(committed_container: Container, tmp_path: Path) -> None:
    c = committed_container
    editorial = EditorialService(c.uow, c.clock)
    editorial.import_dir(write_content(tmp_path / "content"))
    with c.uow() as s:
        admin = create_user(s, c, "jefa@race.example.com", role=UserRole.admin)
        create_user(s, c, "alumna@race.example.com")
        admin_id = admin.id
    revision = next(r for r in editorial.list_revisions() if r["item_slug"] == "u1-checkpoint")
    editorial.approve(uuid.UUID(revision["id"]), by=admin_id, content_hash=revision["content_hash"])
    editorial.publish(uuid.UUID(revision["id"]), by=admin_id)

    app = create_app(c.settings, container=c)
    clients = []
    for _ in range(2):
        client = TestClient(
            app, base_url="https://testserver", headers={"Origin": "http://localhost:5173"}
        )
        clients.append((client, login(client, "alumna@race.example.com")))
    barrier = threading.Barrier(2)
    ids: list[str] = ["", ""]

    def worker(i: int) -> None:
        client, csrf = clients[i]
        barrier.wait()
        res = client.post(
            f"/api/v1/assessments/{revision['item_id']}/start",
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": str(uuid.uuid4())},
        )
        ids[i] = res.json()["id"]

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert ids[0] and ids[0] == ids[1]
