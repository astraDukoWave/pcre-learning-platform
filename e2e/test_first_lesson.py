"""AC-14 (primer tramo): invitación → aceptación con consentimiento → L1: respuesta, pista,
fallo y acierto → recarga con respuestas persistidas → reinicio del servidor sin pérdida →
una segunda cuenta no ve los intentos de la primera."""

from __future__ import annotations

import re

from conftest import STUDENT_EMAIL, Contexts, Server, accept, invite, login
from playwright.sync_api import Page, expect

LESSON_TITLE = "Elegir un curso que encaje con tu horario"


def open_lesson(page: Page) -> None:
    page.get_by_role("link", name="Continuar con tu ruta").click()
    page.wait_for_url("**/ruta")
    page.get_by_role("link", name=LESSON_TITLE).click()
    expect(page.get_by_role("heading", level=1, name=LESSON_TITLE)).to_be_visible()


def test_first_lesson_end_to_end(contexts: Contexts, server: Server) -> None:
    link = invite(contexts.new_page("admin"), "nueva.alumna@example.com")
    student = contexts.new_page("alumna")
    accept(student, link)
    open_lesson(student)

    # Actividad 1: pista, respuesta incorrecta y nota al margen.
    expect(student.get_by_text("Actividad 1 de 5")).to_be_visible()
    student.get_by_role("button", name="Pista (1 de 2)").click()
    expect(student.get_by_text("Primero marca cuándo no puede estudiar Valeria.")).to_be_visible()
    student.get_by_label("Course B, because it is on Saturday, when she does not work.").check()
    student.get_by_role("button", name="Enviar respuesta").click()
    expect(student.get_by_text("Revisa esto")).to_be_visible()
    expect(student.locator("aside mark")).to_contain_text("Course B")
    student.get_by_role("button", name="Siguiente actividad").click()

    # Actividad 2: acierto.
    expect(student.get_by_text("Actividad 2 de 5")).to_be_visible()
    student.get_by_label("Watch a recording of the class at home.").check()
    student.get_by_role("button", name="Enviar respuesta").click()
    expect(student.locator("aside").get_by_text("Correcto")).to_be_visible()

    # Recarga: retoma en la primera actividad sin responder y conserva las respuestas.
    student.reload()
    expect(student.get_by_text("Actividad 3 de 5")).to_be_visible()
    student.get_by_role("button", name=re.compile(r"^1")).click()
    expect(
        student.get_by_label("Course B, because it is on Saturday, when she does not work.")
    ).to_be_checked()
    expect(student.get_by_text("Revisa esto")).to_be_visible()

    # Reinicio del servidor: los intentos confirmados siguen ahí (NFR-02).
    server.restart()
    student.reload()
    expect(student.get_by_text("Actividad 3 de 5")).to_be_visible()

    # Una segunda cuenta no ve los intentos de la primera.
    other = contexts.new_page("otra")
    login(other, STUDENT_EMAIL)
    open_lesson(other)
    expect(other.get_by_text("Actividad 1 de 5")).to_be_visible()
    attempts = other.request.get(f"{server.url}/api/v1/me/attempts")
    assert attempts.ok and attempts.json() == []
