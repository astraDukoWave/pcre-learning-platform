"""REQ-17: textos legales en borrador con la versión igual a `CONSENT_VERSION`, y la ruta
pública con la versión vigente y el contacto de privacidad."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import BACKEND_DIR, Settings

LEGAL = BACKEND_DIR.parent / "frontend" / "src" / "legal"


def test_legal_texts_are_drafts_with_the_consent_version() -> None:
    version = Settings.model_fields["consent_version"].default
    for name in ("privacidad.md", "terminos.md", "como-funciona.md"):
        text = (LEGAL / name).read_text(encoding="utf-8")
        assert f"Versión: {version}" in text, name
        assert "Borrador pendiente de revisión" in text, name
    privacy = (LEGAL / "privacidad.md").read_text(encoding="utf-8")
    for required in (
        "Heroku",
        "Estados Unidos",
        "Acceso",
        "Rectificación",
        "Cancelación",
        "Oposición",
        "{{PRIVACY_CONTACT_EMAIL}}",
        "Cambios a este aviso",
    ):
        assert required in privacy, required


def test_legal_route_is_public(client: TestClient) -> None:
    res = client.get("/api/v1/legal")
    assert res.status_code == 200
    body = res.json()
    assert body["consent_version"] == Settings.model_fields["consent_version"].default
    assert "@" in body["privacy_contact_email"]
