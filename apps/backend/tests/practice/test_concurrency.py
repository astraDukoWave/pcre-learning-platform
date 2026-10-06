"""AC-09: dos envíos concurrentes con la misma clave → un solo intento (dos hilos contra
PostgreSQL real, con commits)."""

from __future__ import annotations

import threading
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.bootstrap import Container
from app.main import create_app
from app.modules.content.service_editorial import EditorialService
from app.modules.identity.models import UserRole
from app.modules.practice.models import Attempt
from tests.content.builder import write_content
from tests.helpers import create_user, login

ORIGIN = {"Origin": "http://localhost:5173"}


def test_concurrent_same_key_creates_one_attempt(
    committed_container: Container, tmp_path: Path
) -> None:
    c = committed_container
    editorial = EditorialService(c.uow, c.clock)
    editorial.import_dir(write_content(tmp_path / "content"))
    with c.uow() as s:
        admin = create_user(s, c, "jefa@race.example.com", role=UserRole.admin)
        student = create_user(s, c, "alumna@race.example.com")
        admin_id, student_id = admin.id, student.id
    revision = next(r for r in editorial.list_revisions() if r["item_slug"] == "u1-l1-lectura")
    editorial.approve(uuid.UUID(revision["id"]), by=admin_id, content_hash=revision["content_hash"])
    detail = editorial.publish(uuid.UUID(revision["id"]), by=admin_id)
    activity = next(a["id"] for a in detail["activities"] if a["key"] == "u1.l1.p1")

    app = create_app(c.settings, container=c)
    clients = []
    for _ in range(2):
        client = TestClient(app, base_url="https://testserver", headers=ORIGIN)
        csrf = login(client, "alumna@race.example.com")
        clients.append((client, csrf))
    key = str(uuid.uuid4())
    barrier = threading.Barrier(2)
    results: list[tuple[int, dict[str, object]]] = [(0, {})] * 2

    def worker(i: int) -> None:
        client, csrf = clients[i]
        barrier.wait()
        res = client.post(
            "/api/v1/attempts",
            json={"activity_id": activity, "response": {"selected": ["b"]}},
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": key},
        )
        results[i] = (res.status_code, res.json())

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert [r[0] for r in results] == [201, 201]
    assert results[0][1] == results[1][1]
    with c.uow() as s:
        attempts = s.scalar(
            select(func.count()).select_from(Attempt).where(Attempt.user_id == student_id)
        )
    assert attempts == 1
