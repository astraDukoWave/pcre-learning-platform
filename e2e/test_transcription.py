"""MVP-02 REQ-04 en el navegador con el micrófono y el transcriptor falsos: grabar → enviar →
transcribir → comparar (repetición) y confirmar o disputar la entrevista antes del feedback.
El audio solo sale del navegador al pedir la transcripción."""

from __future__ import annotations

import re

from conftest import Contexts, new_student
from playwright.sync_api import Page, expect
from test_formats import go_to, open_item, press

TITLE = "Presentarte y hablar de tu rutina"


def record_and_send(page: Page, *, prep: bool) -> None:
    press(page, "Grabar")
    if prep:
        press(page, "Grabar ya")  # salta la preparación
    expect(page.get_by_text(re.compile("Grabando"))).to_be_visible()
    page.wait_for_timeout(1200)
    press(page, "Detener")
    expect(page.get_by_label("Tu grabación")).to_be_visible()
    press(page, "Enviar respuesta")
    expect(page.get_by_role("heading", name="Autoevalúa tu respuesta")).to_be_visible()


def test_repeat_is_transcribed_on_request_and_compared(funded_contexts: Contexts) -> None:
    page = new_student(funded_contexts, "transcribe.repite@example.com")
    uploads: list[str] = []
    page.on("request", lambda r: uploads.append(r.url) if r.method == "POST" else None)
    open_item(page, TITLE)
    go_to(page, 3)
    record_and_send(page, prep=False)
    assert not any("/speaking/transcriptions" in u for u in uploads)  # todavía no
    press(page, "Transcribir mi grabación")
    # Objetivo: «Hi, my name is Daniela, and I work at a travel agency.» (12 palabras); el
    # transcriptor falso devuelve la oración sin «travel».
    expect(page.get_by_text("Palabras reconocidas: 11 de 12")).to_be_visible()
    expect(page.get_by_text("travel", exact=True)).to_be_visible()
    expect(page.get_by_text(re.compile("puede ser el reconocimiento"))).to_be_visible()
    assert sum("/speaking/transcriptions" in u for u in uploads) == 1
    # La autoevaluación sigue: la comparación no es una calificación.
    expect(page.get_by_role("heading", name="Autoevalúa tu respuesta")).to_be_visible()


def test_interview_is_confirmed_before_feedback(funded_contexts: Contexts) -> None:
    page = new_student(funded_contexts, "transcribe.entrevista@example.com")
    open_item(page, TITLE)
    go_to(page, 1)
    record_and_send(page, prep=True)
    press(page, "Transcribir mi grabación")
    expect(page.get_by_text("Esto entendimos:")).to_be_visible()
    expect(page.get_by_text("Hi, my name is Daniela and I work at a agency.")).to_be_visible()
    expect(page.get_by_role("button", name="Pedir feedback (IA)")).to_have_count(0)
    press(page, "Eso no fue lo que dije")
    expect(page.get_by_text(re.compile("no pediremos feedback sobre este texto"))).to_be_visible()
    press(page, "La revisé: sí es lo que dije")
    page.get_by_role("button", name="Pedir feedback (IA)").click()
    expect(page.get_by_text("Feedback automático orientativo (IA)")).to_be_visible()

    page.reload()  # la confirmación y el feedback se guardaron en el intento
    go_to(page, 1)
    expect(page.get_by_text("Esto entendimos:")).to_be_visible()
    expect(page.get_by_text("Feedback automático orientativo (IA)")).to_be_visible()
