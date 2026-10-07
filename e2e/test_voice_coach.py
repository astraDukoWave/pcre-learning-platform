"""MVP-02 AC-14 en el navegador: el coach de voz con el micrófono falso de Chromium (un WAV)
y el Deepgram falso (`apps/backend/tests/fakes/deepgram_agent.py`): aviso y consentimiento,
audio del coach, estados, subtítulos, «Repetir», detener, el feedback con la evidencia
resaltada, «Eso no fue lo que dije» y la valoración; y el modo texto cuando la voz está
apagada. Las capturas quedan en `test-results/coach-*.png` (revisión visual)."""

from __future__ import annotations

import re

from conftest import RESULTS, Contexts, new_student
from playwright.sync_api import Page, WebSocket, expect

SCENARIO = "Informarte para inscribirte a un curso"


def open_scenario(page: Page) -> None:
    page.goto("/ruta")
    page.get_by_role("link", name=SCENARIO).click()
    expect(page.get_by_role("heading", level=1, name=SCENARIO)).to_be_visible()


def test_voice_coach_conversation(funded_contexts: Contexts) -> None:
    page = new_student(funded_contexts, "coach.voz@example.com")
    # Audio del coach: frames binarios que llegan al navegador por el WebSocket de la app.
    audio_frames: list[int] = []
    sockets: list[str] = []

    def watch(ws: WebSocket) -> None:
        sockets.append(ws.url)
        ws.on(
            "framereceived",
            lambda payload: (
                audio_frames.append(len(payload)) if isinstance(payload, bytes) else None
            ),
        )

    page.on("websocket", watch)
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
    # El micrófono falso (el WAV) manda audio: el Deepgram falso responde con turnos del alumno.
    expect(page.get_by_text(re.compile("^Hi, I'd like some information"))).to_be_visible(
        timeout=10_000
    )
    expect(page.get_by_text(re.compile("^How much does the course cost"))).to_be_visible(
        timeout=15_000
    )
    page.get_by_role("button", name="Repetir").click()
    expect(page.get_by_text("Could you repeat that, please?")).to_be_visible()
    page.screenshot(path=str(RESULTS / "coach-live.png"), full_page=True)
    page.get_by_role("button", name="Detener").click()
    expect(page.get_by_text("Terminó la práctica")).to_be_visible(timeout=10_000)
    expect(page.get_by_text("Detuviste la práctica.")).to_be_visible()
    assert any("/ws/voice/" in url for url in sockets)
    assert audio_frames and sum(audio_frames) > 0, "no llegó audio del coach"

    # Feedback final: hasta dos observaciones con la evidencia resaltada en su turno.
    feedback = page.get_by_role("region", name="Feedback de la práctica")
    expect(feedback.get_by_text("Feedback automático orientativo (IA)")).to_be_visible(
        timeout=15_000
    )
    notes = feedback.locator("ol").first.locator("li")
    expect(notes).to_have_count(2)
    expect(notes.first.locator("mark")).to_have_text(re.compile("^Hi, I.d like some"))
    page.get_by_text(re.compile(r"Transcripción \(\d+ turnos\)")).click()
    highlighted = feedback.locator("details li mark")
    expect(highlighted).to_have_count(2)
    expect(highlighted.first).to_contain_text("like some")
    page.screenshot(path=str(RESULTS / "coach-ended.png"), full_page=True)

    # «Eso no fue lo que dije» en el turno citado oculta su observación.
    page.get_by_role("button", name=re.compile(r"Eso no fue lo que dije \(turno 2\)")).click()
    expect(feedback.get_by_text(re.compile("Ocultamos 1 observación"))).to_be_visible()
    expect(feedback.locator("details li mark")).to_have_count(1)
    expect(feedback.get_by_text("Marcaste que no fue lo que dijiste")).to_be_visible()

    # Valoración de la sesión.
    page.get_by_role("radio", name="4").check()
    page.get_by_role("button", name="Enviar valoración").click()
    expect(page.get_by_text("Gracias: tu valoración", exact=False)).to_be_visible()
    page.screenshot(path=str(RESULTS / "coach-feedback.png"), full_page=True)


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


def test_coach_by_keyboard_with_axe_and_reduced_motion(funded_contexts: Contexts) -> None:
    """NFR-08: el coach se opera solo con teclado, sin violaciones graves ni críticas de axe
    antes, durante y al terminar, y sin animación con movimiento reducido."""
    from test_accessibility import axe, with_axe

    page = with_axe(new_student(funded_contexts, "coach.teclado@example.com"))
    page.emulate_media(reduced_motion="reduce")
    open_scenario(page)
    page.get_by_role("link", name="Practicar este escenario por voz con el coach").click()
    expect(page.get_by_text("Aviso de procesamiento de voz")).to_be_visible()
    axe(page, "coach: antes de empezar")

    consent = page.get_by_label("Guardar la transcripción y el feedback en mi progreso")
    consent.focus()
    page.keyboard.press("Space")
    expect(consent).to_be_checked()
    page.keyboard.press("Tab")
    expect(page.get_by_role("button", name="Empezar")).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.get_by_text(re.compile("^Hi, I'd like some information"))).to_be_visible(
        timeout=10_000
    )
    expect(page.get_by_text(re.compile("^How much does the course cost"))).to_be_visible(
        timeout=15_000
    )
    status = page.get_by_role("status").filter(
        has_text=re.compile("Te escucho|El coach está hablando")
    )
    animation = status.locator("span").first.evaluate("el => getComputedStyle(el).animationName")
    assert animation == "none", f"el indicador se anima con movimiento reducido: {animation}"
    axe(page, "coach: conversación")

    stop = page.get_by_role("button", name="Detener")
    for _ in range(30):
        if stop.evaluate("el => el === document.activeElement"):
            break
        page.keyboard.press("Tab")
    expect(stop).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.get_by_text("Terminó la práctica")).to_be_visible(timeout=10_000)
    feedback = page.get_by_role("region", name="Feedback de la práctica")
    expect(feedback.get_by_text("Feedback automático orientativo (IA)")).to_be_visible(
        timeout=15_000
    )
    summary = feedback.get_by_text(re.compile(r"Transcripción \(\d+ turnos\)"))
    summary.focus()
    page.keyboard.press("Enter")
    dispute = page.get_by_role("button", name=re.compile(r"Eso no fue lo que dije \(turno 2\)"))
    dispute.focus()
    page.keyboard.press("Enter")
    expect(feedback.get_by_text(re.compile("Ocultamos 1 observación"))).to_be_visible()
    axe(page, "coach: al terminar")
