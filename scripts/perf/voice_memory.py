"""Memoria con tres sesiones de voz simultáneas (MVP-02 NFR-06, AC-16).

Arranca el Deepgram falso (`apps/backend/tests/fakes/deepgram_agent.py`) y el servidor con las
banderas de WebSocket de `heroku.yml` (`--ws-max-size 1048576`, un worker), crea tres alumnos
por invitación, abre tres sesiones de voz y manda frames de 1 MiB (el máximo) a más de 50 por
segundo durante `--seconds`. Mide el RSS del proceso del servidor (`/proc/<pid>/status`) cada
medio segundo. Umbral: 300 MB. No es un gate de CI: el resultado se registra en el reporte de
verify. Nunca toca un proveedor real ni producción.

Preparación y corrida (desde `apps/backend`, con una base desechable):

    export DATABASE_URL=postgresql+psycopg://pcre:pcre@localhost:5432/pcre_migcheck
    uv run python ../../scripts/dev/dbtool.py reset
    uv run python -m app.cli release
    APP_ENV=dev uv run python -m app.cli dev-seed
    uv run python ../../scripts/perf/voice_memory.py --markdown /tmp/voice-memory.md

Sale con 0 si el RSS máximo queda bajo el umbral y las tres sesiones corrieron; con 1 si no.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import socket
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import websockets

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND))

from tests.fakes.deepgram_agent import FakeDeepgramAgent  # noqa: E402

SESSION_COOKIE = "__Host-pcre_session"
FRAME = b"\x00" * (1024 * 1024)
THRESHOLD_MB = 300.0
PASSWORD = "practica-local-1"  # noqa: S105 (cuenta de prueba de dev-seed)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def rss_mb(pid: int) -> float:
    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) / 1024
    return 0.0


def start_server(port: int, agent_url: str) -> subprocess.Popen[bytes]:
    env = {
        **os.environ,
        "APP_ENV": "dev",
        "LOG_LEVEL": "WARNING",
        "LOG_SALT": "perf",
        "DEV_ALLOWED_ORIGINS": f"http://localhost:{port}",
        "VOICE_ENABLED": "true",
        "VOICE_PROVIDER": "fake",
        "VOICE_AGENT_URL": agent_url,
        "BUDGET_GLOBAL_MONTHLY_MICROUSD": "50000000",
        "BUDGET_USER_MONTHLY_MICROUSD": "5000000",
        "VOICE_MAX_MINUTES_PER_USER_MONTH": "600",
    }
    process = subprocess.Popen(  # noqa: S603
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--workers",
            "1",
            "--ws-max-size",
            "1048576",
            "--ws-max-queue",
            "8",
            "--ws-per-message-deflate",
            "false",
        ],
        cwd=BACKEND,
        env=env,
    )
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            if httpx.get(f"http://127.0.0.1:{port}/health", timeout=1).status_code == 200:
                return process
        except httpx.HTTPError:
            time.sleep(0.2)
    process.terminate()
    raise SystemExit("el servidor no arrancó")


def keep_session(client: httpx.Client) -> None:
    """La cookie de sesión es `Secure`: en http local se manda a mano desde el jar."""
    client.headers["Cookie"] = f"{SESSION_COOKIE}={client.cookies.get(SESSION_COOKIE)}"


def students(base: str, origin: str, admin_email: str, count: int) -> list[httpx.Client]:
    """Alumnos nuevos por invitación (la cuenta admin la crea `dev-seed`)."""
    admin = httpx.Client(base_url=base, headers={"Origin": origin})
    res = admin.post(
        "/api/v1/auth/login", json={"email": admin_email, "password": PASSWORD}
    ).raise_for_status()
    admin_csrf = res.json()["csrf_token"]
    keep_session(admin)
    consent = admin.get("/api/v1/legal").raise_for_status().json()["consent_version"]
    clients = []
    for _ in range(count):
        email = f"voz-{uuid.uuid4().hex[:8]}@example.com"
        link = admin.post(
            "/api/v1/admin/invitations",
            json={"email": email},
            headers={"X-CSRF-Token": admin_csrf},
        ).raise_for_status()
        token = parse_qs(urlsplit(link.json()["url"]).fragment)["t"][0]  # /aceptar#t=…
        client = httpx.Client(base_url=base, headers={"Origin": origin})
        client.post(
            "/api/v1/auth/invitations/accept",
            json={
                "token": token,
                "password": PASSWORD,
                "password_confirm": PASSWORD,
                "accept_privacy": True,
                "consent_version": consent,
                "adult": True,
            },
        ).raise_for_status()
        keep_session(client)
        clients.append(client)
    return clients


def scenario_id(client: httpx.Client) -> str:
    paths = client.get("/api/v1/learning-paths").raise_for_status().json()
    path = client.get(f"/api/v1/learning-paths/{paths[0]['id']}").raise_for_status().json()
    for unit in path["units"]:
        for item in unit["items"]:
            if item["kind"] == "scenario":
                return str(item["id"])
    raise SystemExit("no hay escenario publicado: corre dev-seed")


async def session(
    client: httpx.Client, base_ws: str, origin: str, scenario: str, seconds: float
) -> dict[str, Any]:
    me = client.get("/api/v1/me").raise_for_status().json()
    created = (
        client.post(
            "/api/v1/voice-sessions",
            json={"scenario_id": scenario, "accept_voice_notice": True},
            headers={"X-CSRF-Token": me["csrf_token"], "Idempotency-Key": str(uuid.uuid4())},
        )
        .raise_for_status()
        .json()
    )
    cookie = client.cookies.get(SESSION_COOKIE)
    sent = received = 0
    async with websockets.connect(
        base_ws + created["ws_path"],
        additional_headers={"Origin": origin, "Cookie": f"{SESSION_COOKIE}={cookie}"},
        max_size=4 * 1024 * 1024,
    ) as ws:

        async def drain() -> None:
            nonlocal received
            async for _ in ws:
                received += 1

        reader = asyncio.create_task(drain())
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            await ws.send(FRAME)
            sent += 1
            await asyncio.sleep(1 / 60)  # por encima del límite de 50 por segundo
        await ws.send(json.dumps({"type": "stop"}))
        await asyncio.sleep(1)
        reader.cancel()
    return {"session": created["id"], "frames_sent": sent, "messages_received": received}


async def run(
    clients: list[httpx.Client], base_ws: str, origin: str, scenario: str, seconds: float, pid: int
) -> tuple[list[dict[str, Any]], list[float]]:
    samples: list[float] = []

    async def sample() -> None:
        while True:
            samples.append(rss_mb(pid))
            await asyncio.sleep(0.5)

    sampler = asyncio.create_task(sample())
    results = await asyncio.gather(
        *(session(c, base_ws, origin, scenario, seconds) for c in clients)
    )
    sampler.cancel()
    return list(results), samples


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seconds", type=float, default=15.0)
    parser.add_argument("--admin-email", default="admin@example.com")
    parser.add_argument("--markdown", type=Path, default=None)
    args = parser.parse_args(argv)
    port = free_port()
    origin = f"http://localhost:{port}"
    with FakeDeepgramAgent() as fake:
        server = start_server(port, fake.url)
        try:
            idle = rss_mb(server.pid)
            base = f"http://127.0.0.1:{port}"
            clients = students(base, origin, args.admin_email, 3)
            scenario = scenario_id(clients[0])
            results, samples = asyncio.run(
                run(clients, f"ws://127.0.0.1:{port}", origin, scenario, args.seconds, server.pid)
            )
        finally:
            server.terminate()
            server.wait(timeout=15)
    peak = max(samples) if samples else 0.0
    ok = peak < THRESHOLD_MB and all(r["frames_sent"] > 0 for r in results) and len(results) == 3
    report = {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "python": platform.python_version(),
        "sessions": len(results),
        "seconds": args.seconds,
        "frame_bytes": len(FRAME),
        "rss_idle_mb": round(idle, 1),
        "rss_peak_mb": round(peak, 1),
        "threshold_mb": THRESHOLD_MB,
        "provider_frames_received": sum(c.audio_bytes for c in fake.connections) // len(FRAME),
        "results": results,
        "ok": ok,
    }
    print(json.dumps(report, indent=2))
    if args.markdown:
        args.markdown.write_text(
            "| Medición | Valor |\n| --- | --- |\n"
            + "\n".join(f"| {k} | {v} |" for k, v in report.items() if k != "results")
            + "\n",
            encoding="utf-8",
        )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
