"""E2E con Playwright (Python): servidor uvicorn real, frontend compilado, PostgreSQL de
prueba y proveedores falsos (MVP-01 AC-14).

- La base `pcre_e2e` se vacía, se migra y se importa con `python -m app.cli release`, y
  `dev-seed` crea las cuentas de prueba y publica el contenido con el revisor `fixture:dev`.
- El contenido es una copia de `content/` en `test-results/e2e-content/` con el audio
  pendiente reemplazado por tonos WAV de prueba marcados como revisados: así se publican la
  escucha y la repetición sin TTS. La copia nunca vuelve a `content/` (el lint de `content/`
  rechaza audio que no sea del proveedor real).
- `server.restart()` reinicia el proceso (NFR-02: reiniciar no pierde intentos).
- Si una prueba falla, su traza queda en `test-results/` (artefacto de la CI).

Correr: `make e2e` (necesita `apps/frontend/dist` y Chromium). Fuera de la CI, si Playwright
no tiene su navegador, `PW_CHROMIUM_EXECUTABLE` apunta a un Chromium instalado.
"""

from __future__ import annotations

import hashlib
import io
import math
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import time
import urllib.request
import wave
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import yaml
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
DIST = ROOT / "apps" / "frontend" / "dist"
RESULTS = ROOT / "test-results"
DATABASE_URL = os.environ.get(
    "E2E_DATABASE_URL", "postgresql+psycopg://pcre:pcre@127.0.0.1:5432/pcre_e2e"
)
PASSWORD = "practica-local-1"  # noqa: S105 (cuenta de prueba de dev-seed)
ADMIN_EMAIL = "admin@example.com"
STUDENT_EMAIL = "alumna@example.com"


def _tone(seconds: float = 1.0, hz: int = 440, rate: int = 8000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = (
            struct.pack("<h", int(8000 * math.sin(2 * math.pi * hz * i / rate)))
            for i in range(int(seconds * rate))
        )
        w.writeframes(b"".join(frames))
    return buf.getvalue()


def prepare_content(dest: Path) -> Path:
    """Copia de `content/` con el audio pendiente como tono de prueba revisado."""
    sys.path.insert(0, str(BACKEND))
    from app.modules.content.schema import AudioEntry, script_hash

    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(ROOT / "content", dest)
    for manifest in dest.glob("*/audio/manifest.yaml"):
        data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {"audio": []}
        for entry in data["audio"]:
            if entry.get("reviewed_by"):
                continue
            audio = _tone()
            name = f"e2e-{entry['id']}.wav"
            (manifest.parent / name).write_bytes(audio)
            entry.update(
                {
                    "file": name,
                    "sha256": hashlib.sha256(audio).hexdigest(),
                    "script_hash": script_hash(AudioEntry.model_validate(entry)),
                    "provider": "e2e-fixture",
                    "model": "tone",
                    "reviewed_by": "fixture:e2e",
                    "reviewed_at": "2026-10-06",
                }
            )
        manifest.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return dest


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _run(args: list[str], env: dict[str, str]) -> None:
    subprocess.run(args, cwd=BACKEND, env=env, check=True)  # noqa: S603


@dataclass
class Server:
    port: int
    env: dict[str, str]
    process: subprocess.Popen[bytes] | None = None
    log: Path = field(default_factory=lambda: RESULTS / "server.log")

    @property
    def url(self) -> str:
        # `localhost` y no 127.0.0.1: Chromium la trata como origen seguro y conserva la
        # cookie `__Host-pcre_session` (Secure) sin HTTPS.
        return f"http://localhost:{self.port}"

    def start(self) -> None:
        self.log.parent.mkdir(parents=True, exist_ok=True)
        out = self.log.open("ab")
        self.process = subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
            ],
            cwd=BACKEND,
            env=self.env,
            stdout=out,
            stderr=subprocess.STDOUT,
        )
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                health = f"http://127.0.0.1:{self.port}/health"
                with urllib.request.urlopen(health, timeout=1) as res:
                    if res.status == 200:
                        return
            except OSError:
                time.sleep(0.2)
        raise RuntimeError(f"el servidor no arrancó; ver {self.log}")

    def stop(self) -> None:
        if self.process is not None:
            self.process.terminate()
            self.process.wait(timeout=15)
            self.process = None

    def restart(self) -> None:
        self.stop()
        self.start()


@pytest.fixture(scope="session")
def server() -> Iterator[Server]:
    if not (DIST / "index.html").exists():
        pytest.fail("falta apps/frontend/dist: corre `npm run build` en apps/frontend")
    port = _free_port()
    content = prepare_content(RESULTS / "e2e-content")
    env = {
        **os.environ,
        "APP_ENV": "test",
        "DATABASE_URL": DATABASE_URL,
        "FRONTEND_DIST": str(DIST),
        "LOG_LEVEL": "WARNING",
        "LOG_SALT": "e2e",
        "TEST_CLOCK_ENABLED": "true",
        "CONTENT_DIR": str(content),
        "MEDIA_DIR": str(content / "toefl-ibt-2026-b1-b2" / "audio"),
        "DEV_ALLOWED_ORIGINS": f"http://localhost:{port},http://127.0.0.1:{port}",
    }
    _run([sys.executable, "../../scripts/dev/dbtool.py", "reset"], env)
    _run([sys.executable, "-m", "app.cli", "release"], env)
    _run(
        [
            sys.executable,
            "-m",
            "app.cli",
            "dev-seed",
            "--admin-email",
            ADMIN_EMAIL,
            "--student-email",
            STUDENT_EMAIL,
            "--password",
            PASSWORD,
        ],
        env,
    )
    srv = Server(port=port, env=env)
    srv.start()
    yield srv
    srv.stop()


# Capacidades con costo encendidas con dobles y presupuesto de prueba (MVP-02). Nunca hay
# llaves: los proveedores son los falsos de `adapters/` y `tests/fakes/`.
FUNDED_ENV = {
    "AI_FEEDBACK_ENABLED": "true",
    "FEEDBACK_PROVIDER": "fake",
    "BUDGET_GLOBAL_MONTHLY_MICROUSD": "25000000",
    "BUDGET_USER_MONTHLY_MICROUSD": "8000000",
    "VOICE_MAX_MINUTES_PER_USER_MONTH": "60",
    "GEMINI_PRICE_INPUT_PER_MTOK_MICROUSD": "100000",
    "GEMINI_PRICE_OUTPUT_PER_MTOK_MICROUSD": "400000",
}


@pytest.fixture(scope="session")
def funded_server(server: Server) -> Iterator[Server]:
    """Segundo proceso sobre la misma base ya preparada, con las capacidades de MVP-02
    encendidas y sus dobles; el servidor principal las deja apagadas (AC-02)."""
    port = _free_port()
    env = {
        **server.env,
        **FUNDED_ENV,
        "DEV_ALLOWED_ORIGINS": f"http://localhost:{port},http://127.0.0.1:{port}",
    }
    srv = Server(port=port, env=env, log=RESULTS / "server-funded.log")
    srv.start()
    yield srv
    srv.stop()


@pytest.fixture(scope="session")
def playwright() -> Iterator[Playwright]:
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(playwright: Playwright) -> Iterator[Browser]:
    executable = os.environ.get("PW_CHROMIUM_EXECUTABLE") or None
    # Micrófono falso con el permiso concedido (en Chrome Headless Shell, el de la CI, sin
    # `fake-ui` getUserMedia no funciona) y audio sin gesto previo. La denegación se simula
    # por página (`deny_microphone`).
    args = [
        "--use-fake-device-for-media-stream",
        "--use-fake-ui-for-media-stream",
        "--autoplay-policy=no-user-gesture-required",
    ]
    browser = playwright.chromium.launch(executable_path=executable, args=args)
    yield browser
    browser.close()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> Iterator[None]:
    outcome = yield
    report = outcome.get_result()  # type: ignore[attr-defined]
    setattr(item, f"rep_{report.when}", report)


class Contexts:
    """Contextos de navegador por persona; guarda la traza si la prueba falla."""

    def __init__(
        self, browser: Browser, server: Server, name: str, viewport: dict[str, int] | None
    ) -> None:
        self.browser, self.server, self.name, self.viewport = browser, server, name, viewport
        self.opened: list[tuple[str, BrowserContext]] = []

    def new_page(self, who: str) -> Page:
        kwargs = {"base_url": self.server.url}
        if self.viewport:
            kwargs["viewport"] = self.viewport  # type: ignore[assignment]
        context = self.browser.new_context(**kwargs)  # type: ignore[arg-type]
        context.tracing.start(screenshots=True, snapshots=True)
        context.set_default_timeout(10_000)
        self.opened.append((who, context))
        return context.new_page()

    def close(self, failed: bool) -> None:
        for who, context in self.opened:
            if failed:
                RESULTS.mkdir(parents=True, exist_ok=True)
                context.tracing.stop(path=str(RESULTS / f"{self.name}-{who}.zip"))
            else:
                context.tracing.stop()
            context.close()


@pytest.fixture
def contexts(
    request: pytest.FixtureRequest, browser: Browser, server: Server
) -> Iterator[Contexts]:
    viewport = getattr(request, "param", None)
    ctx = Contexts(browser, server, request.node.name, viewport)
    yield ctx
    report = getattr(request.node, "rep_call", None)
    ctx.close(failed=bool(report and report.failed))


@pytest.fixture
def funded_contexts(
    request: pytest.FixtureRequest, browser: Browser, funded_server: Server
) -> Iterator[Contexts]:
    ctx = Contexts(browser, funded_server, request.node.name, None)
    yield ctx
    report = getattr(request.node, "rep_call", None)
    ctx.close(failed=bool(report and report.failed))


def login(page: Page, email: str, password: str = PASSWORD) -> None:
    page.goto("/entrar")
    page.get_by_label("Correo").fill(email)
    page.get_by_label("Contraseña").fill(password)
    page.get_by_role("button", name="Entrar").click()
    page.wait_for_url("**/inicio")


def invite(admin: Page, email: str) -> str:
    login(admin, ADMIN_EMAIL)
    admin.goto("/admin/usuarios")
    admin.get_by_label("Correo").fill(email)
    admin.get_by_role("button", name="Crear invitación").click()
    link = admin.locator("code").filter(has_text="/aceptar#t=")
    expect(link).to_be_visible()
    return link.inner_text().strip()


def accept(page: Page, link: str) -> None:
    page.goto(link)
    expect(page.get_by_text("Te invitaron con el correo")).to_be_visible()
    page.get_by_label("Contraseña", exact=True).fill("una frase segura de prueba")
    page.get_by_label("Confirma tu contraseña").fill("una frase segura de prueba")
    page.get_by_label(re.compile("Leí y acepto")).check()
    page.get_by_label(re.compile("mayor de edad")).check()
    page.get_by_role("button", name="Crear mi acceso").click()
    page.wait_for_url("**/bienvenida")
    page.get_by_role("button", name="Guardar y continuar").click()
    page.wait_for_url("**/inicio")


def cli_invite(server: Server, email: str) -> str:
    """Invitación por la CLI (sin iniciar sesión de admin: el límite de login es por
    correo). El flujo de invitación por la interfaz lo cubre `test_first_lesson`."""
    out = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "app.cli", "invite", "--email", email],
        cwd=BACKEND,
        env=server.env,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    found = re.search(r"/aceptar#t=(\S+)", out)
    assert found, out
    return f"/aceptar#t={found.group(1)}"


def new_student(contexts: Contexts, email: str) -> Page:
    """Cuenta nueva por invitación: cada prueba con su alumno, sin depender del orden."""
    link = cli_invite(contexts.server, email)
    page = contexts.new_page(email.split("@", maxsplit=1)[0])
    accept(page, link)
    return page


def deny_microphone(page: Page) -> None:
    """Desde la siguiente navegación, getUserMedia rechaza como cuando la persona niega el
    permiso (`NotAllowedError`), igual en Chromium y en Chrome Headless Shell."""
    page.context.add_init_script(
        "navigator.mediaDevices.getUserMedia = () => "
        "Promise.reject(new DOMException('Permission denied', 'NotAllowedError'));"
    )
