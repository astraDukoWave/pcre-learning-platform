"""AC-11 y EDGE-13: revisiones, hallazgos, aprobación por hash, publicación atómica y retiro."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.content.models import ContentItem, ContentRevision, EditorialDecision
from app.modules.content.service_editorial import EditorialService
from tests.content.builder import PATH_SLUG, add_listening, write_content
from tests.helpers import Account

BASE = "/api/v1/admin/content"


def _rev(admin: Account, slug: str, status: str | None = None) -> dict[str, Any]:
    rows = admin.client.get(
        f"{BASE}/revisions", params={"status": status} if status else None
    ).json()
    return next(r for r in rows if r["item_slug"] == slug)


def _approve(admin: Account, rev: dict[str, Any], content_hash: str | None = None) -> Any:
    return admin.client.post(
        f"{BASE}/revisions/{rev['id']}/approve",
        json={"content_hash": content_hash or rev["content_hash"], "note": "revisado"},
        headers=admin.headers(),
    )


def _publish(admin: Account, rev_id: str) -> Any:
    return admin.client.post(f"{BASE}/revisions/{rev_id}/publish", json={}, headers=admin.headers())


def test_detail_shows_author_view_preview_sources_and_checklist(
    admin: Account, imported: Path
) -> None:
    rev = _rev(admin, "u1-l1-lectura")
    detail = admin.client.get(f"{BASE}/revisions/{rev['id']}").json()
    assert detail["status"] == "draft"
    assert detail["activities"][0]["solution"] == {"correct": ["a"], "why": {"b": "Es en sábado."}}
    assert detail["sources"] and {s["key"] for s in detail["sources"]} >= {"ets-toefl-ibt-content"}
    assert len(detail["checklist"]) == 9
    assert detail["preview_practice"]["activities"][0]["aids"]
    assert all(a["aids"] == [] for a in detail["preview_assessment"]["activities"])
    assert detail["blockers"]["publish"] == ["not_approved"]


def test_approval_is_bound_to_the_hash(admin: Account, imported: Path) -> None:
    rev = _rev(admin, "u1-l1-lectura")
    res = _approve(admin, rev, content_hash="0" * 64)
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "hash_mismatch"
    ok = _approve(admin, rev)
    assert ok.status_code == 200
    assert ok.json()["approved_hash"] == rev["content_hash"]
    again = _approve(admin, rev)
    assert again.status_code == 409 and again.json()["error"]["code"] == "not_draft"


def test_material_finding_blocks_until_resolved(admin: Account, imported: Path) -> None:
    rev = _rev(admin, "u1-l1-lectura")
    finding = admin.client.post(
        f"{BASE}/revisions/{rev['id']}/findings",
        json={
            "category": "answer_key",
            "severity": "material",
            "description": "La clave del ítem 2 es discutible.",
        },
        headers=admin.headers(),
    ).json()
    assert finding["author"].startswith("user:")
    blocked = _approve(admin, rev)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "open_material_findings"
    assert "Hay hallazgos materiales abiertos." in blocked.json()["error"]["message"]
    admin.client.patch(
        f"{BASE}/findings/{finding['id']}",
        json={"status": "resolved", "resolution_note": "Se reescribió el distractor."},
        headers=admin.headers(),
    )
    assert _approve(admin, rev).status_code == 200
    minor = admin.client.post(
        f"{BASE}/revisions/{rev['id']}/findings",
        json={"category": "typo", "severity": "minor", "description": "Coma de más."},
        headers=admin.headers(),
    )
    assert minor.status_code == 201
    assert _publish(admin, rev["id"]).status_code == 200  # un hallazgo menor no bloquea


def test_pending_audio_blocks_approval(
    admin: Account, editorial: EditorialService, tmp_path: Path
) -> None:
    editorial.import_dir(write_content(tmp_path / "c", lambda f: add_listening(f, reviewed=False)))
    rev = _rev(admin, "u1-l2-escucha")
    assert rev["audio_pending"] is True
    res = _approve(admin, rev)
    assert res.status_code == 409 and res.json()["error"]["code"] == "audio_pending"


def test_publish_is_atomic_and_supersedes(
    admin: Account, student: Account, editorial: EditorialService, imported: Path, db: Session
) -> None:
    v1 = _rev(admin, "u1-l1-lectura")
    assert _publish(admin, v1["id"]).json()["error"]["code"] == "not_approved"
    _approve(admin, v1)
    assert _publish(admin, v1["id"]).status_code == 200
    item = db.scalar(select(ContentItem).where(ContentItem.slug == "u1-l1-lectura"))
    assert item is not None
    lesson = student.client.get(f"/api/v1/lessons/{item.id}").json()
    assert lesson["revision_version"] == 1

    file = imported / PATH_SLUG / "units/u1/l1-lectura.yaml"
    data = yaml.safe_load(file.read_text())
    data["title"] = "Elegir un curso, versión revisada"
    file.write_text(yaml.safe_dump(data, allow_unicode=True))
    editorial.import_dir(imported)
    # La publicada sigue vigente mientras la nueva está en borrador.
    assert student.client.get(f"/api/v1/lessons/{item.id}").json()["revision_version"] == 1
    v2 = next(
        r
        for r in admin.client.get(f"{BASE}/revisions").json()
        if r["item_slug"] == "u1-l1-lectura" and r["version"] == 2
    )
    _approve(admin, v2)
    assert _publish(admin, v2["id"]).status_code == 200
    db.expire_all()
    statuses = dict(
        db.execute(
            select(ContentRevision.version, ContentRevision.status).where(
                ContentRevision.item_id == item.id
            )
        ).all()
    )
    assert statuses == {1: "superseded", 2: "published"}
    assert student.client.get(f"/api/v1/lessons/{item.id}").json()["revision_version"] == 2
    actions = db.scalars(
        select(EditorialDecision.action).order_by(EditorialDecision.created_at)
    ).all()
    assert actions.count("publish") == 2


def test_withdraw_requires_reason_and_keeps_history(
    admin: Account, student: Account, imported: Path, db: Session
) -> None:
    rev = _rev(admin, "u1-escenario")
    _approve(admin, rev)
    _publish(admin, rev["id"])
    item_id = admin.client.get(f"{BASE}/revisions/{rev['id']}").json()["item"]["id"]
    assert student.client.get(f"/api/v1/scenarios/{item_id}").status_code == 200
    empty = admin.client.post(
        f"{BASE}/revisions/{rev['id']}/withdraw", json={"reason": " "}, headers=admin.headers()
    )
    assert empty.status_code == 409 and empty.json()["error"]["code"] == "reason_required"
    res = admin.client.post(
        f"{BASE}/revisions/{rev['id']}/withdraw",
        json={"reason": "Corrección de la clave"},
        headers=admin.headers(),
    )
    assert res.status_code == 200 and res.json()["status"] == "withdrawn"
    assert student.client.get(f"/api/v1/scenarios/{item_id}").status_code == 404
    assert db.get(ContentRevision, rev["id"]) is not None  # el historial queda


def test_publish_unit_publishes_all_approved(admin: Account, imported: Path) -> None:
    for slug in ("u1-l1-lectura", "u1-l3-escritura"):
        _approve(admin, _rev(admin, slug))
    unit_id = next(u["id"] for u in admin.client.get(f"{BASE}/units").json() if u["position"] == 1)
    res = admin.client.post(f"{BASE}/units/{unit_id}/publish", headers=admin.headers())
    assert res.status_code == 200
    assert sorted(p["item_slug"] for p in res.json()) == ["u1-l1-lectura", "u1-l3-escritura"]
    again = admin.client.post(f"{BASE}/units/{unit_id}/publish", headers=admin.headers())
    assert again.status_code == 409


def test_editorial_routes_are_admin_only(student: Account, imported: Path) -> None:
    assert student.client.get(f"{BASE}/revisions").status_code == 403
    res = student.client.post(
        f"{BASE}/units/{'0' * 8}-0000-4000-8000-{'0' * 12}/publish", headers=student.headers()
    )
    assert res.status_code == 403
