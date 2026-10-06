"""AC-14 (tramo de repasos) y REQ-09: un fallo programa el repaso; con el reloj de prueba
+25 h la sesión vence por inactividad, el repaso aparece en el inicio, se responde, el
progreso lo cuenta como revisión diferida y se cierra la sesión."""

from __future__ import annotations

import re

from conftest import Contexts, Server, login, new_student
from playwright.sync_api import Page, expect

PASSWORD = "una frase segura de prueba"  # noqa: S105 (cuenta de prueba creada en el E2E)
EMAIL = "repasos@example.com"


def move_clock(page: Page, server: Server, **body: object) -> None:
    url = f"{server.url}/api/test/clock"
    res = page.request.post(url, data=body, headers={"Origin": server.url})
    assert res.ok, res.text()


def test_failure_becomes_a_due_review_the_next_day(contexts: Contexts, server: Server) -> None:
    page = new_student(contexts, EMAIL)
    try:
        start = page.get_by_role("link", name=re.compile("^Empezar: Elegir un curso"))
        expect(start).to_be_visible()
        start.click()
        page.get_by_label("Course B, because it is on Saturday, when she does not work.").check()
        page.get_by_role("button", name="Enviar respuesta").click()
        expect(page.get_by_text("Revisa esto")).to_be_visible()

        page.goto("/inicio")
        expect(page.get_by_text("ninguno por ahora")).to_be_visible()
        resume = page.get_by_role("link", name=re.compile("^Continuar: Elegir un curso"))
        expect(resume).to_be_visible()

        # Al día siguiente: la sesión venció por inactividad y el repaso ya está vencido.
        move_clock(page, server, advance_hours=25)
        page.goto("/inicio")
        page.wait_for_url("**/entrar**")
        login(page, EMAIL, PASSWORD)
        expect(page.get_by_role("link", name="1 para hoy")).to_be_visible()
        page.get_by_role("link", name="1 para hoy").click()
        expect(page.get_by_text(re.compile("Unidad 1 · Lectura"))).to_be_visible()
        page.get_by_label("The Lunch Club, because it ends before he starts work.").check()
        page.get_by_role("button", name="Enviar respuesta").click()
        expect(page.locator("aside").get_by_text("Correcto")).to_be_visible()
        page.get_by_role("button", name="Siguiente repaso").click()
        expect(page.get_by_text("No tienes repasos pendientes")).to_be_visible()

        page.get_by_role("link", name="Progreso").click()
        expect(page.get_by_text("1 de 1 repasos correctos")).to_be_visible()
        expect(page.get_by_text(re.compile(r"Unidad 1 · Lectura \(U1\.R\)"))).to_be_visible()

        page.get_by_role("button", name="Salir").click()
        page.wait_for_url("**/entrar")
    finally:
        move_clock(page, server, reset=True)
