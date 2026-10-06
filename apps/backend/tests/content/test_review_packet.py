"""`scripts/content/review_packet.py` (MVP-03 REQ-08, AC-16 de MVP-01): el paquete es
determinista, cubre todos los ítems de la unidad con el hash que muestra el panel y está al
día en `docs/contenido/revision/`."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from app.modules.content.lint import lint_dir
from app.modules.content.schema import content_hash, item_payload

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts" / "content" / "review_packet.py"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("review_packet", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_unit_packet_lists_every_item_with_its_hash_and_checklist() -> None:
    packet = load_script()
    text = packet.render("u1")
    assert text == packet.render("u1")  # sin fechas: la CI puede compararlo
    bundle, _ = lint_dir(ROOT / "content")["toefl-ibt-2026-b1-b2"]
    unit_items = [m for m in bundle.valid_items if (m.unit or "").startswith("u1-")]
    assert len(unit_items) == 6  # 4 lecciones, escenario y checkpoint
    for model in unit_items:
        assert f"`{content_hash(item_payload(model))[:12]}`" in text
        for act in model.activities:
            assert f"**`{act.key}`**" in text
    assert text.count("### Lista de revisión (contrato §12)") == 6
    assert "**pendiente**" in text  # las fuentes sin consultar se ven como pendientes
    assert "u1-l2-aviso-biblioteca" in text and "sin revisar" in text


def test_form_packet_and_selector() -> None:
    packet = load_script()
    text = packet.render("inicial")
    assert "Formulario de ruta: diagnóstico inicial" in text
    assert "**`dx.r1`**" in text and "u1.l1.p1" not in text
    assert packet.main(["--unit", "u9"]) == 2


def test_committed_packets_are_up_to_date() -> None:
    packet = load_script()
    for path in sorted((ROOT / "docs" / "contenido" / "revision").glob("*.md")):
        assert path.read_text(encoding="utf-8") == packet.render(path.stem), path.name
