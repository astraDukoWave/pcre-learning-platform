"""MVP-02 REQ-06 en el navegador: el coach de voz con el micrófono falso de Chromium y el
Deepgram falso (`apps/backend/tests/fakes/deepgram_agent.py`): aviso y consentimiento,
estados, subtítulos, una ayuda, detener y el resumen; y el modo texto cuando la voz está
apagada. Las capturas quedan en `test-results/coach-*.png` (revisión visual de CS-06)."""

from __future__ import annotations

import re

from conftest import RESULTS, Contexts, new_student
from playwright.sync_api import Page, expect

SCENARIO = "Informarte para inscribirte a un curso"


def open_scenario(page: Page) -> None:
    page.goto("/ruta")
    page.get_by_role("link", name=SCENARIO).click()
    expect(page.get_by_role("heading", level=1, name=SCENARIO)).to_be_visible()


def test_voice_coach_conversation(funded_contexts: Contexts) -> None:
    page = new_student(funded_contexts, "coach.voz@example.com")
    open_scenario(page)
    page.get_by_role("link", name="Practicar este escenario por voz con el coach").click()
    expect(page.get_by_text("Aviso de procesamiento de voz")).to_be_visible()
    page.get_by_label("Guardar la transcripción y el feedback en mi progreso").check()
    page.screenshot(path=str(RESULTS / "coach-intro.png"), full_page=True)
    page.get_by_role("button", name="Empezar").click()
    expect(page.get_by_text(re.compile("^Good afternoon, Lakeside Language Center"))).to_be_visible(
        timeout=10_000
    )
    expect(
        page.get_by_role("status").filter(has_text=re.compile("Te escucho|El coach está hablando"))
    ).to_be_visible()
    # El micrófono falso manda audio: el Deepgram falso responde con un turno del alumno.
    expect(page.get_by_text(re.compile("^Hi, I'd like some information"))).to_be_visible(
        timeout=10_000
    )
    page.get_by_role("button", name="Repetir").click()
    expect(page.get_by_text("Could you repeat that, please?")).to_be_visible()
    page.screenshot(path=str(RESULTS / "coach-live.png"), full_page=True)
    page.get_by_role("button", name="Detener").click()
    expect(page.get_by_text("Terminó la práctica")).to_be_visible(timeout=10_000)
    expect(page.get_by_text("Detuviste la práctica.")).to_be_visible()
    expect(page.get_by_text(re.compile(r"Transcripción \(\d+ turnos\)"))).to_be_visible()
    page.screenshot(path=str(RESULTS / "coach-ended.png"), full_page=True)


def test_without_voice_the_scenario_is_practiced_by_text(contexts: Contexts) -> None:
    page = new_student(contexts, "coach.apagado@example.com")
    open_scenario(page)
    expect(
        page.get_by_role("link", name="Practicar este escenario por voz con el coach")
    ).to_have_count(0)
    scenario_url = page.url
    page.goto(scenario_url + "/voz")
    expect(page.get_by_text("La práctica por voz no está disponible ahora.")).to_be_visible()
    expect(page.get_by_role("button", name="Empezar")).to_have_count(0)
    page.get_by_role("link", name="Practicar este escenario por texto").click()
    expect(page.get_by_text("Práctica en modo texto.", exact=False)).to_be_visible()
