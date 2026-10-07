"""REQ-10 por formato con teclado (MVP-01 CS-06): completado, orden, escritura con
autoevaluación y reformulación, diálogo guiado, escucha con conteo de reproducciones y
transcripción servida, y habla con grabación local y con el micrófono denegado."""

from __future__ import annotations

import re

from conftest import Contexts, deny_microphone, new_student
from playwright.sync_api import Page, expect

PATH = "/ruta"


def open_item(page: Page, title: str) -> None:
    page.goto(PATH)
    page.get_by_role("link", name=title).click()
    expect(page.get_by_role("heading", level=1, name=title)).to_be_visible()


def go_to(page: Page, n: int) -> None:
    page.get_by_role("navigation", name="Actividades de la lección").get_by_role(
        "button", name=re.compile(rf"^{n}")
    ).click()


def press(page: Page, name: str) -> None:
    """Activa un botón con el teclado (foco + Enter), sin clic."""
    page.get_by_role("button", name=name, exact=True).focus()
    page.keyboard.press("Enter")


def test_completion_order_and_writing_with_keyboard(contexts: Contexts) -> None:
    page = new_student(contexts, "formatos.escritura@example.com")

    # Completado (L1, actividad 5): se escribe lo que falta o la palabra completa.
    open_item(page, "Elegir un curso que encaje con tu horario")
    go_to(page, 5)
    page.get_by_label(re.compile(r"^Hueco 1 de 5")).focus()
    for text in ("se", "dy", "recordings", "ore", "lars"):
        page.keyboard.type(text)
        page.keyboard.press("Tab")
    press(page, "Enviar respuesta")
    expect(page.locator("aside").get_by_text("Correcto")).to_be_visible()

    # Orden de fichas (L3, actividad 1): agregar con Enter y mover con las flechas.
    open_item(page, "Pedir información por escrito")
    for token in ("Could you", "tell me", "what time", "starts?", "the class"):
        press(page, token)
    placed = page.get_by_role("button", name="the class, posición 5")
    placed.focus()
    page.keyboard.press("Enter")  # seleccionar
    page.keyboard.press("ArrowLeft")  # mover antes de "starts?"
    expect(page.get_by_role("button", name="the class, posición 4")).to_be_visible()
    press(page, "Enviar respuesta")
    expect(page.locator("aside").get_by_text("Correcto")).to_be_visible()

    # Correo (L3, actividad 4): contador, envío, autoevaluación y luego el ejemplo.
    go_to(page, 4)
    area = page.get_by_role("textbox")
    area.focus()
    page.keyboard.type(
        "Dear Northside, I am writing to ask about the evening classes. Could you tell me "
        "which days the classes meet and how much the course costs? I would also like to "
        "know if the classes are recorded, because I sometimes work late. Thank you, Ana"
    )
    counter = re.compile(r"^\d+ palabras · objetivo: entre 50 y 110")
    expect(page.get_by_text(counter)).to_be_visible()
    press(page, "Enviar respuesta")
    expect(page.get_by_role("heading", name="Autoevalúa tu respuesta")).to_be_visible()
    expect(page.get_by_text("Ejemplo comentado", exact=True)).to_have_count(0)  # antes, la rúbrica
    criteria = ("Cumplimiento de la tarea", "Organización", "Control del lenguaje", "Registro")
    for criterion in criteria:
        group = page.get_by_role("group", name=criterion)
        group.get_by_role("radio").first.focus()
        page.keyboard.press("ArrowRight")  # nivel 1
        page.keyboard.press("ArrowRight")  # nivel 2
    press(page, "Guardar autoevaluación")
    expect(page.get_by_text("Ejemplo comentado", exact=True)).to_be_visible()
    marks = re.compile("Tu autoevaluación: Cumplimiento de la tarea 2/3")
    expect(page.get_by_text(marks)).to_be_visible()

    # Reformular: intento nuevo ligado al anterior, con el texto anterior para editar.
    press(page, "Reformular")
    expect(page.get_by_text("Estás reformulando")).to_be_visible()
    expect(page.get_by_role("textbox")).to_have_value(re.compile("^Dear Northside"))


def test_guided_dialogue_with_keyboard(contexts: Contexts) -> None:
    page = new_student(contexts, "formatos.dialogo@example.com")
    open_item(page, "Informarte para inscribirte a un curso")
    expect(page.get_by_text(re.compile("No es una tarea del examen oficial"))).to_be_visible()
    for option in (
        "Hi. I'd like some information about the evening English classes, please.",
        "Could you tell me how much it costs per month?",
        "OK. Is there still space in the Monday group?",
        "Yes. What do I need to bring to the interview?",
        "Perfect, thank you for your help. I'll come on Monday.",
    ):
        press(page, option)
    expect(page.get_by_text("La conversación terminó.")).to_be_visible()
    press(page, "Enviar respuesta")
    expect(page.locator("aside").get_by_text("Lo lograste")).to_be_visible()
    expect(page.get_by_text("5 de 5 respuestas fueron adecuadas")).to_be_visible()
    expect(page.get_by_text(re.compile("Pregunta indirecta: más cortés"))).to_be_visible()


def test_listening_counts_plays_and_serves_the_transcript(contexts: Contexts) -> None:
    page = new_student(contexts, "formatos.escucha@example.com")
    open_item(page, "Escuchar avisos y responder a preguntas")
    expect(page.get_by_text("Aún no lo escuchas.")).to_be_visible()
    audio = page.get_by_label("Audio de la actividad")
    audio.evaluate("a => a.play()")
    expect(page.get_by_text("Lo escuchaste 1 vez.")).to_be_visible()
    expect(page.get_by_text("Attention, please.")).to_have_count(0)  # la transcripción no viaja
    press(page, "Transcripción")
    expect(page.get_by_text(re.compile("^Attention, please."))).to_be_visible()
    page.get_by_label("To explain a change in the library's closing time.").focus()
    page.keyboard.press("Space")
    press(page, "Enviar respuesta")
    expect(page.locator("aside").get_by_text("Correcto")).to_be_visible()
    expect(page.get_by_text("Lo resolviste con ayuda")).to_be_visible()


def test_speaking_records_locally_and_handles_a_denied_microphone(contexts: Contexts) -> None:
    title = "Presentarte y hablar de tu rutina"
    page = new_student(contexts, "formatos.habla@example.com")
    uploads: list[str] = []
    page.on("request", lambda r: uploads.append(r.url) if r.method == "POST" else None)
    open_item(page, title)
    expect(
        page.get_by_text(re.compile(r"^Tu grabación se queda en tu dispositivo\."))
    ).to_be_visible()
    press(page, "Grabar")
    press(page, "Grabar ya")  # salta la preparación
    expect(page.get_by_text(re.compile("Grabando"))).to_be_visible()
    press(page, "Detener")
    expect(page.get_by_label("Tu grabación")).to_be_visible()
    press(page, "Enviar respuesta")
    expect(page.get_by_role("heading", name="Autoevalúa tu respuesta")).to_be_visible()
    # Sin pedir la transcripción, el audio no se sube (y aquí está apagada: AC-02).
    assert not any("/speaking/transcriptions" in u for u in uploads), uploads
    assert all("/api/v1/" in u for u in uploads), uploads
    unavailable = re.compile("La transcripción automática no está disponible")
    expect(page.get_by_text(unavailable)).to_be_visible()
    expect(page.get_by_role("button", name="Transcribir mi grabación")).to_have_count(0)

    denied = new_student(contexts, "formatos.sinmicro@example.com")
    deny_microphone(denied)
    open_item(denied, title)
    press(denied, "Grabar")
    press(denied, "Grabar ya")
    expect(denied.get_by_text("No pude grabar")).to_be_visible()
    press(denied, "Continuar sin grabar")
    press(denied, "Enviar respuesta")
    expect(denied.get_by_text("No se evaluó porque no hubo grabación.")).to_be_visible()
    expect(denied.get_by_text("Ejemplo comentado", exact=True)).to_be_visible()
