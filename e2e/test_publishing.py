"""AC-14 (tramo editorial) y REQ-15: un admin aprueba y publica desde el panel una revisión
nueva de L1; quien estaba a mitad de la lección conserva su revisión y su historial
(EDGE-04), quien empieza después recibe la nueva, la completa y la valora; el reporte de un
problema llega al triage y el panel del piloto lo refleja."""

from __future__ import annotations

import re
import subprocess
import sys

from conftest import ADMIN_EMAIL, BACKEND, RESULTS, Contexts, Server, login, new_student
from playwright.sync_api import Page, expect

LESSON = "Elegir un curso que encaje con tu horario"
L1_FILE = (
    RESULTS
    / "e2e-content"
    / "toefl-ibt-2026-b1-b2"
    / "units"
    / "u1-informacion-decisiones"
    / "l1-lectura.yaml"
)
OLD = "Localizarás horarios, costos y límites en un anuncio"
NEW = "Encontrarás horarios, costos y límites en un anuncio"


def open_lesson(page: Page) -> None:
    page.goto("/ruta")
    page.get_by_role("link", name=LESSON).click()
    expect(page.get_by_role("heading", level=1, name=LESSON)).to_be_visible()


def answer(page: Page, label: str) -> None:
    page.get_by_label(label).check()
    page.get_by_role("button", name="Enviar respuesta").click()
    expect(page.locator("aside")).to_be_visible()


def import_new_draft(server: Server) -> None:
    """Simula un cambio de contenido en el repo: el importador crea la revisión v2 como
    borrador; aprobar y publicar siguen siendo acciones humanas en el panel."""
    L1_FILE.write_text(L1_FILE.read_text(encoding="utf-8").replace(OLD, NEW), encoding="utf-8")
    subprocess.run(  # noqa: S603
        [sys.executable, "-m", "app.cli", "content", "import", "--dir", str(L1_FILE.parents[3])],
        cwd=BACKEND,
        env=server.env,
        check=True,
        capture_output=True,
    )


def test_admin_publishes_a_new_revision_and_history_stays(
    contexts: Contexts, server: Server
) -> None:
    early = new_student(contexts, "antes@example.com")
    open_lesson(early)
    expect(early.get_by_text(OLD)).to_be_visible()
    answer(early, "Course B, because it is on Saturday, when she does not work.")
    early.get_by_role("button", name="Reportar un problema").click()
    early.get_by_label("¿Qué pasa?").select_option("answer_key")
    early.get_by_label("Detalle (opcional)").fill("Creo que la B también sirve.")
    early.get_by_role("button", name="Enviar reporte").click()
    expect(early.get_by_text("Gracias por avisar")).to_be_visible()

    import_new_draft(server)
    admin = contexts.new_page("admin")
    login(admin, ADMIN_EMAIL)
    admin.goto("/admin/contenido")
    admin.get_by_label("Estado").select_option("draft")
    admin.get_by_role("link", name=LESSON).click()
    expect(admin.get_by_role("heading", level=1, name=f"{LESSON} · v2")).to_be_visible()
    admin.get_by_role("button", name=re.compile("^Aprobar el hash")).click()
    admin.get_by_role("button", name="Publicar esta revisión").click()
    expect(admin.get_by_text("Estado: Publicada")).to_be_visible()

    # Quien estaba a mitad de la lección sigue en v1 con su respuesta (EDGE-04).
    early.reload()
    expect(early.get_by_text(OLD)).to_be_visible()
    early.get_by_role("navigation", name="Actividades de la lección").get_by_role(
        "button", name=re.compile(r"^1")
    ).click()
    expect(
        early.get_by_label("Course B, because it is on Saturday, when she does not work.")
    ).to_be_checked()

    # Quien empieza después recibe v2, la completa y la valora.
    late = new_student(contexts, "despues@example.com")
    open_lesson(late)
    expect(late.get_by_text(NEW)).to_be_visible()
    for label in (
        "Course A, because it meets on three weekday evenings.",
        "Watch a recording of the class at home.",
        "70 dollars",
        "Its small groups give her more chances to ask questions.",
    ):
        answer(late, label)
        late.get_by_role("button", name="Siguiente actividad").click()
    late.get_by_label(re.compile(r"^Hueco 1 de 5")).fill("course")
    late.get_by_label(re.compile(r"^Hueco 2 de 5")).fill("study")
    late.get_by_label(re.compile(r"^Hueco 3 de 5")).fill("recording")
    late.get_by_label(re.compile(r"^Hueco 4 de 5")).fill("before")
    late.get_by_label(re.compile(r"^Hueco 5 de 5")).fill("dollars")
    late.get_by_role("button", name="Enviar respuesta").click()
    late.get_by_role("button", name="Terminar").click()
    expect(late.get_by_text("Completaste la lección")).to_be_visible()
    late.get_by_role("group", name="¿Qué tan útil fue esta lección?").get_by_label("4").check()
    late.get_by_label("Comentario (opcional)").fill("El ejemplo del horario me ayudó.")
    late.get_by_role("button", name="Enviar valoración").click()
    expect(late.get_by_text("Gracias: tu valoración ayuda")).to_be_visible()

    # Triage del reporte y panel del piloto.
    admin.goto("/admin/reportes")
    card = admin.get_by_role("article").filter(has_text="Creo que la B también sirve.")
    card.get_by_label("Estado").select_option("resolved")
    card.get_by_role("button", name="Guardar").click()
    expect(admin.get_by_text("No hay reportes con este estado.")).to_be_visible()
    admin.goto("/admin/piloto")
    rating = admin.get_by_role("row", name=re.compile(LESSON))
    expect(rating).to_contain_text("4")
    expect(admin.get_by_text("El ejemplo del horario me ayudó.")).to_be_visible()
