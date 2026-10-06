from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.helpers import Account


@pytest.fixture
def lesson(admin: Account, imported: Path) -> dict[str, Any]:
    """Publica la lección de lectura y el escenario de la ruta de prueba."""
    ids: dict[str, Any] = {}
    for rev in admin.client.get("/api/v1/admin/content/revisions").json():
        if rev["item_slug"] not in ("u1-l1-lectura", "u1-escenario", "u1-checkpoint"):
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
        detail = res.json()
        ids[rev["item_slug"]] = {
            "item_id": rev["item_id"],
            "revision_id": rev["id"],
            "activities": {a["key"]: a["id"] for a in detail["activities"]},
        }
    return ids
