"""AC-15 y NFR-08: axe sin violaciones graves ni críticas en acceso, inicio, ruta, lección,
comprobación y resultados, con viewport de escritorio y de teléfono (390 × 844); un
recorrido solo con teclado; `prefers-reduced-motion` respetado."""

from __future__ import annotations

import re
from typing import Any

import pytest
from conftest import ROOT, Contexts, new_student
from playwright.sync_api import Page, expect

AXE = ROOT / "apps" / "frontend" / "node_modules" / "axe-core" / "axe.min.js"
PHONE = {"width": 390, "height": 844}
LESSON = "Elegir un curso que encaje con tu horario"
TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]


def with_axe(page: Page) -> Page:
    """Carga axe-core como script de inicio del contexto: la CSP de la app (`script-src
    'self'`) bloquea con razón un `<script>` inyectado, no un script de inicio."""
    page.context.add_init_script(path=str(AXE))
    return page


def axe(page: Page, screen: str) -> None:
    """Corre axe-core y falla con las violaciones graves o críticas, con su regla y nodos."""
    result: dict[str, Any] = page.evaluate(
        "tags => axe.run(document, {runOnly: {type: 'tag', values: tags}})", TAGS
    )
    bad = [v for v in result["violations"] if v["impact"] in ("serious", "critical")]
    detail = [f"{v['id']} ({v['impact']}): {[n['target'] for n in v['nodes']][:3]}" for v in bad]
    assert not bad, f"{screen}: {detail}"


@pytest.mark.parametrize("contexts", [None, PHONE], indirect=True, ids=["desktop", "phone"])
def test_main_screens_have_no_serious_axe_violations(contexts: Contexts) -> None:
    phone = contexts.viewport is not None
    visitor = with_axe(contexts.new_page("visitante"))
    visitor.goto("/entrar")
    expect(visitor.get_by_role("button", name="Entrar")).to_be_visible()
    axe(visitor, "acceso")

    email = f"axe-{'telefono' if phone else 'escritorio'}@example.com"
    page = with_axe(new_student(contexts, email))
    page.reload()
    expect(page.get_by_role("link", name=re.compile("^Empezar:"))).to_be_visible()
    axe(page, "inicio")

    page.goto("/ruta")
    expect(page.get_by_role("link", name=LESSON)).to_be_visible()
    axe(page, "ruta")

    page.get_by_role("link", name=LESSON).click()
    page.get_by_label("Course B, because it is on Saturday, when she does not work.").check()
    page.get_by_role("button", name="Enviar respuesta").click()
    expect(page.get_by_text("Revisa esto")).to_be_visible()
    axe(page, "lección con feedback")

    page.goto("/ruta")
    page.get_by_role("link", name="Checkpoint de la unidad 1").click()
    page.get_by_role("button", name="Empezar").click()
    page.wait_for_url("**/corridas/*")
    expect(page.get_by_text("Pregunta 1 de")).to_be_visible()
    axe(page, "comprobación")

    page.get_by_role("navigation", name="Preguntas de la comprobación").get_by_role(
        "button", name="Enviar", exact=True
    ).click()
    page.get_by_role("button", name="Enviar comprobación").click()
    expect(page.get_by_role("heading", name="Resultados por objetivo")).to_be_visible()
    axe(page, "resultados")

    if phone:  # sin desplazamiento horizontal en teléfono
        overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        assert overflow <= 0, f"desborde horizontal de {overflow}px"


def test_keyboard_only_journey(contexts: Contexts) -> None:
    """Entrar, abrir la lección y responder solo con el teclado."""
    page = new_student(contexts, "teclado@example.com")
    page.get_by_role("button", name="Salir").focus()
    page.keyboard.press("Enter")
    page.wait_for_url("**/entrar")

    skip = page.get_by_role("link", name="Saltar al contenido")
    skip.focus()
    page.keyboard.press("Enter")  # el enlace de salto lleva al contenido principal
    expect(page.locator("main#main")).to_be_focused()
    page.get_by_label("Correo").focus()
    page.keyboard.type("teclado@example.com")
    page.keyboard.press("Tab")
    expect(page.get_by_label("Contraseña")).to_be_focused()
    page.keyboard.type("una frase segura de prueba")
    page.keyboard.press("Enter")
    page.wait_for_url("**/inicio")

    start = page.get_by_role("link", name=re.compile("^Empezar:"))
    for _ in range(30):  # se llega al enlace principal tabulando, sin ratón
        page.keyboard.press("Tab")
        if start.evaluate("el => el === document.activeElement"):
            break
    expect(start).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.get_by_role("heading", level=1, name=LESSON)).to_be_visible()

    page.get_by_label("Course A, because it meets on three weekday evenings.").focus()
    page.keyboard.press("Space")
    send = page.get_by_role("button", name="Enviar respuesta")
    for _ in range(30):
        page.keyboard.press("Tab")
        if send.evaluate("el => el === document.activeElement"):
            break
    expect(send).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator("aside").get_by_text("Correcto")).to_be_visible()


def test_reduced_motion_disables_the_marker_animation(contexts: Contexts) -> None:
    page = new_student(contexts, "movimiento@example.com")
    page.emulate_media(reduced_motion="reduce")
    page.goto("/ruta")
    page.get_by_role("link", name=LESSON).click()
    page.get_by_label("Course B, because it is on Saturday, when she does not work.").check()
    page.get_by_role("button", name="Enviar respuesta").click()
    mark = page.locator("aside mark").first
    expect(mark).to_be_visible()
    duration = mark.evaluate("el => parseFloat(getComputedStyle(el).animationDuration)")
    assert duration < 0.001, f"la animación dura {duration}s con movimiento reducido"
