"""REQ-12 de extremo a extremo (MVP-01 CS-07): diagnóstico (subconjunto) con respuestas
guardadas sin feedback, retomar tras recargar (EDGE-17), audio "no pude escucharlo"
(EDGE-07), envío con resultados por objetivo y diagnóstico único (EDGE-09); checkpoint
repetible con corridas numeradas."""

from __future__ import annotations

import re

from conftest import Contexts, new_student
from playwright.sync_api import Locator, Page, expect

LABEL = "Comprobación formativa: no es un examen oficial"


def open_form(page: Page, title: str) -> None:
    page.goto("/ruta")
    page.get_by_role("link", name=title).click()
    expect(page.get_by_role("heading", level=1, name=title)).to_be_visible()


def save_and_next(page: Page) -> None:
    page.get_by_role("button", name=re.compile("^Guardar y (seguir|revisar)$")).click()


def test_diagnostic_subset_resume_and_results(contexts: Contexts) -> None:
    page = new_student(contexts, "diagnostico@example.com")
    page.goto("/ruta")
    expect(page.get_by_text("Empieza por el diagnóstico inicial")).to_be_visible()
    open_form(page, "Diagnóstico inicial")
    expect(page.get_by_text(LABEL)).to_be_visible()
    page.get_by_role("button", name="Empezar").click()
    page.wait_for_url("**/corridas/*")

    # Pregunta 1 (lectura): respuesta guardada sin feedback.
    expect(page.get_by_text("Pregunta 1 de 16")).to_be_visible()
    expect(page.get_by_role("button", name=re.compile("^Pista"))).to_have_count(0)
    page.get_by_label("Call the building office by Tuesday.").check()
    save_and_next(page)
    expect(page.get_by_text("Pregunta 2 de 16")).to_be_visible()
    expect(page.get_by_text("Revisa esto")).to_have_count(0)
    expect(page.locator("aside")).to_have_count(0)  # sin nota al margen antes de enviar

    # Recargar a mitad: la corrida se retoma con la respuesta guardada (EDGE-17).
    page.reload()
    expect(page.get_by_text("Pregunta 2 de 16")).to_be_visible()
    page.get_by_label("Call the office to report brown water.").check()  # respuesta incorrecta
    save_and_next(page)

    # Pregunta 7 (escucha): el audio "no cargó" y queda no evaluable.
    nav = page.get_by_role("navigation", name="Preguntas de la comprobación")
    nav.get_by_role("button", name=re.compile(r"^7")).click()
    expect(page.get_by_text("Pregunta 7 de 16")).to_be_visible()
    page.get_by_role("button", name="No pude escuchar el audio").click()
    expect(page.get_by_text("Pregunta 8 de 16")).to_be_visible()

    # Enviar con el resto sin responder.
    nav.get_by_role("button", name="Enviar", exact=True).click()
    expect(page.get_by_text("Guardaste 3 de 16 respuestas.")).to_be_visible()
    page.get_by_role("button", name="Enviar comprobación").click()
    expect(page.get_by_role("heading", name="Resultados por objetivo")).to_be_visible()

    def row(name: str) -> Locator:
        return page.get_by_role("row", name=re.compile(name))

    expect(row("Unidad 2 · Lectura")).to_contain_text("1 de 1")
    expect(row("Unidad 3 · Lectura")).to_contain_text("0 de 1")
    expect(row("Unidad 1 · Escucha")).to_contain_text("no evaluable (audio)")
    expect(page.get_by_text("No evaluable (audio): no cuenta en tus resultados.")).to_be_visible()
    expect(page.get_by_text("Corrida 1 · la que se compara")).to_be_visible()

    # El diagnóstico no se repite sin un reinicio de admin (EDGE-09).
    open_form(page, "Diagnóstico inicial")
    expect(page.get_by_text("Ya hiciste el diagnóstico.")).to_be_visible()
    expect(page.get_by_role("link", name=re.compile("Corrida 1"))).to_be_visible()


def test_checkpoint_repeats_with_numbered_runs(contexts: Contexts) -> None:
    page = new_student(contexts, "checkpoint@example.com")
    open_form(page, "Checkpoint de la unidad 1")
    page.get_by_role("button", name="Empezar").click()
    page.wait_for_url("**/corridas/*")
    page.get_by_label("Beginner Yoga on Monday or Wednesday.").check()
    save_and_next(page)
    page.get_by_role("navigation", name="Preguntas de la comprobación").get_by_role(
        "button", name="Enviar", exact=True
    ).click()
    page.get_by_role("button", name="Enviar comprobación").click()
    expect(page.get_by_role("heading", name="Resultados por objetivo")).to_be_visible()

    open_form(page, "Checkpoint de la unidad 1")
    page.get_by_role("button", name="Empezar otra corrida").click()
    page.wait_for_url("**/corridas/*")
    expect(page.get_by_text("Corrida 2 · repaso (la comparable es la primera)")).to_be_visible()
