"""E2E con Playwright (Python): servidor uvicorn real, frontend compilado, PostgreSQL de
prueba y proveedores falsos (MVP-01 AC-14).

- La base `pcre_e2e` se vacía, se migra y se importa con `python -m app.cli release`, y
  `dev-seed` crea las cuentas de prueba y publica el contenido con el revisor `fixture:dev`.
- `server.restart()` reinicia el proceso (NFR-02: reiniciar no pierde intentos).
- Si una prueba falla, su traza queda en `test-results/` (artefacto de la CI).

Correr: `make e2e` (necesita `apps/frontend/dist` y Chromium). Fuera de la CI, si Playwright
no tiene su navegador, `PW_CHROMIUM_EXECUTABLE` apunta a un Chromium instalado.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

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
    env = {
        **os.environ,
        "APP_ENV": "test",
        "DATABASE_URL": DATABASE_URL,
        "FRONTEND_DIST": str(DIST),
        "LOG_LEVEL": "WARNING",
        "LOG_SALT": "e2e",
        "TEST_CLOCK_ENABLED": "true",
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


@pytest.fixture(scope="session")
def playwright() -> Iterator[Playwright]:
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(playwright: Playwright) -> Iterator[Browser]:
    executable = os.environ.get("PW_CHROMIUM_EXECUTABLE") or None
    browser = playwright.chromium.launch(executable_path=executable)
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


def login(page: Page, email: str, password: str = PASSWORD) -> None:
    page.goto("/entrar")
    page.get_by_label("Correo").fill(email)
    page.get_by_label("Contraseña").fill(password)
    page.get_by_role("button", name="Entrar").click()
    page.wait_for_url("**/inicio")
