"""Smoke de rendimiento (NFR-03): p95 con 10 peticiones concurrentes por endpoint.

Mide `GET /me`, `GET /learning-paths/{id}`, `GET /lessons/{id}`, `POST /attempts` y
`GET /me/progress` contra un servidor ya arrancado (el build de producción local: SPA
compilada y el comando `run.web` de `heroku.yml` con `APP_ENV=prod`). No es un gate de CI:
el resultado se registra en `docs/reviews/` y, si p95 ≥ 800 ms, se anota una desviación.
Nunca se corre contra producción: crea intentos con la cuenta que recibe.

Preparación y corrida (desde `apps/backend`, con una base desechable; pasos en
`docs/runbook.md` §"Smoke de rendimiento"):

    export DATABASE_URL=postgresql+psycopg://pcre:pcre@localhost:5432/pcre_migcheck
    uv run python ../../scripts/dev/dbtool.py reset
    uv run python -m app.cli release
    APP_ENV=dev uv run python -m app.cli dev-seed --student-email perf@example.com
    (cd ../frontend && npm run build)
    APP_ENV=prod APP_ORIGIN=http://localhost:8000 LOG_LEVEL=WARNING LOG_SALT=perf PORT=8000 \\
      uv run sh -c "$(uv run python ../../scripts/ci/heroku_cmd.py web)" &
    uv run python ../../scripts/perf/smoke.py --base-url http://localhost:8000 \\
      --email perf@example.com --password practica-local-1 --markdown out.md

Sale con 0 si todos los p95 están bajo el umbral y no hubo errores; con 1 si no.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import statistics
import sys
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

SESSION_COOKIE = "__Host-pcre_session"


@dataclass
class Result:
    endpoint: str
    requests: int
    errors: int
    p50_ms: float
    p95_ms: float
    max_ms: float


def p95(samples: list[float]) -> float:
    """Percentil 95 por rango más cercano."""
    ordered = sorted(samples)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


class Api:
    """Cliente con la sesión de una cuenta. La cookie `__Host-` es `Secure`: se manda a mano
    para poder medir sobre `http://localhost` sin TLS."""

    def __init__(self, base_url: str, concurrency: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=30,
            limits=httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency),
            headers={"Origin": self.base_url, "Accept": "application/json"},
        )
        self.auth: dict[str, str] = {}

    def login(self, email: str, password: str) -> None:
        res = self.client.post("/api/v1/auth/login", json={"email": email, "password": password})
        res.raise_for_status()
        session = res.cookies.get(SESSION_COOKIE)
        if session is None:
            raise SystemExit("el login no devolvió la cookie de sesión")
        self.client.cookies.clear()
        csrf = res.json()["csrf_token"]
        self.auth = {"Cookie": f"{SESSION_COOKIE}={session}", "X-CSRF-Token": csrf}

    def get(self, path: str) -> httpx.Response:
        return self.client.get(path, headers=self.auth)

    def post(self, path: str, body: dict[str, Any], **headers: str) -> httpx.Response:
        return self.client.post(path, json=body, headers={**self.auth, **headers})


def targets(api: Api) -> dict[str, Callable[[], httpx.Response]]:
    """Resuelve ids reales (ruta, primera lección publicada y su primera actividad de opción)."""
    paths = api.get("/api/v1/learning-paths").json()
    if not paths:
        raise SystemExit("no hay rutas activas: corre `release` y `dev-seed` antes")
    path_id = paths[0]["id"]
    state = api.get(f"/api/v1/learning-paths/{path_id}").json()
    lesson_id = next(
        item["id"]
        for unit in state["units"]
        for item in unit["items"]
        if item["kind"] == "lesson" and item["state"] != "locked"
    )
    lesson = api.get(f"/api/v1/lessons/{lesson_id}").json()
    activity = next(a for a in lesson["activities"] if a["format"] == "choice")
    option = activity["data"]["options"][0]["id"]

    def attempt() -> httpx.Response:
        return api.post(
            "/api/v1/attempts",
            {"activity_id": activity["id"], "response": {"selected": [option]}},
            **{"Idempotency-Key": str(uuid.uuid4())},
        )

    return {
        "GET /me": lambda: api.get("/api/v1/me"),
        "GET /learning-paths/{id}": lambda: api.get(f"/api/v1/learning-paths/{path_id}"),
        "GET /lessons/{id}": lambda: api.get(f"/api/v1/lessons/{lesson_id}"),
        "POST /attempts": attempt,
        "GET /me/progress": lambda: api.get("/api/v1/me/progress"),
    }


def measure(
    name: str, call: Callable[[], httpx.Response], requests: int, concurrency: int
) -> Result:
    call()  # calentamiento: no cuenta

    def one(_: int) -> tuple[float, bool]:
        started = time.perf_counter()
        res = call()
        return (time.perf_counter() - started) * 1000, res.status_code >= 400

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        samples = list(pool.map(one, range(requests)))
    times = [t for t, _ in samples]
    return Result(
        endpoint=name,
        requests=requests,
        errors=sum(1 for _, failed in samples if failed),
        p50_ms=round(statistics.median(times), 1),
        p95_ms=round(p95(times), 1),
        max_ms=round(max(times), 1),
    )


def markdown(results: list[Result], args: argparse.Namespace) -> str:
    lines = [
        f"Smoke de rendimiento · {datetime.now(UTC):%Y-%m-%d %H:%M} UTC · {args.base_url}",
        f"{args.requests} peticiones por endpoint, {args.concurrency} concurrentes; "
        f"umbral p95 < {args.threshold_ms:.0f} ms; Python {platform.python_version()} "
        f"en {platform.system()} {platform.machine()}",
        "",
        "| Endpoint | Peticiones | Errores | p50 (ms) | p95 (ms) | Máx. (ms) | NFR-03 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | :---: |",
    ]
    for r in results:
        ok = "✅" if r.p95_ms < args.threshold_ms and r.errors == 0 else "❌"
        lines.append(
            f"| `{r.endpoint}` | {r.requests} | {r.errors} | {r.p50_ms} | {r.p95_ms} "
            f"| {r.max_ms} | {ok} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--requests", type=int, default=100, help="por endpoint")
    parser.add_argument("--threshold-ms", type=float, default=800.0)
    parser.add_argument("--markdown", help="guarda la tabla en este archivo")
    parser.add_argument("--json", help="guarda los resultados en este archivo")
    args = parser.parse_args(argv)

    api = Api(args.base_url, args.concurrency)
    api.login(args.email, args.password)
    results = [
        measure(name, call, args.requests, args.concurrency) for name, call in targets(api).items()
    ]
    table = markdown(results, args)
    print(table)
    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as fh:
            fh.write(table)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump([asdict(r) for r in results], fh, indent=2)
    passed = all(r.p95_ms < args.threshold_ms and r.errors == 0 for r in results)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
