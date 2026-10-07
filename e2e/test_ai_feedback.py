"""MVP-02 REQ-02 en el navegador: feedback de escritura con el evaluador falso (notas al
margen con la evidencia resaltada, 👍/👎 y lo guardado al recargar) y AC-02 en la interfaz:
sin presupuesto, la alternativa es la autoevaluación."""

from __future__ import annotations

from conftest import Contexts, new_student
from playwright.sync_api import Page, expect

LESSON = "Pedir información por escrito"
EMAIL = (
    "Dear Northside, I am writing to ask about the evening classes. Could you tell me which "
    "days the classes meet and how much the course costs? I would also like to know if the "
    "classes are recorded, because I sometimes work late. Thank you, Ana"
)


def write_email(page: Page) -> None:
    page.goto("/ruta")
    page.get_by_role("link", name=LESSON).click()
    page.get_by_role("navigation", name="Actividades de la lección").get_by_role(
        "button", name="4"
    ).click()
    page.get_by_role("textbox").fill(EMAIL)
    page.get_by_role("button", name="Enviar respuesta").click()
    expect(page.get_by_text("Tu texto se guardó")).to_be_visible()


def test_writing_feedback_with_the_fake_evaluator(funded_contexts: Contexts) -> None:
    page = new_student(funded_contexts, "feedback.ia@example.com")
    write_email(page)
    page.get_by_role("button", name="Pedir feedback (IA)").click()
    expect(page.get_by_text("Feedback automático orientativo (IA)")).to_be_visible()
    marks = page.locator("section[aria-label='Feedback con IA'] mark")
    expect(marks.first).to_be_visible()
    assert marks.first.inner_text().split("\n")[0].strip().rstrip("0123456789") in EMAIL
    page.get_by_role("group", name="¿Te sirvió la observación 1?").get_by_role(
        "button", name="Me sirvió", exact=True
    ).click()
    expect(page.get_by_text("Gracias por decirnos.")).to_be_visible()
    expect(page.get_by_text("Ejemplo comentado", exact=True)).to_be_visible()

    page.reload()  # lo guardado vuelve sin otra llamada
    page.get_by_role("navigation", name="Actividades de la lección").get_by_role(
        "button", name="4"
    ).click()
    expect(page.get_by_text("Feedback automático orientativo (IA)")).to_be_visible()
    expect(page.get_by_role("button", name="Pedir feedback (IA)")).to_have_count(0)


def test_without_budget_the_alternative_is_self_assessment(contexts: Contexts) -> None:
    page = new_student(contexts, "feedback.apagado@example.com")
    write_email(page)
    page.get_by_role("button", name="Pedir feedback (IA)").click()
    expect(
        page.get_by_text(
            "El feedback no está disponible ahora. Puedes autoevaluarte con la rúbrica."
        )
    ).to_be_visible()
    expect(page.get_by_role("heading", name="Autoevalúa tu respuesta")).to_be_visible()
