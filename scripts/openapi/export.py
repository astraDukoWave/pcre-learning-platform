"""Exporta el OpenAPI de la app sin levantar servidor (ADR-07).

Uso (desde apps/backend): `uv run python ../../scripts/openapi/export.py [--out RUTA]`.
Por defecto escribe `docs/api/openapi.json`. No toca la base de datos.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "backend"))
os.environ["APP_ENV"] = "test"
os.environ["APP_NAME"] = "PCRE"
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://openapi:openapi@127.0.0.1:5432/openapi")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "api" / "openapi.json")
    args = parser.parse_args()

    from app.core.config import Settings
    from app.main import create_app

    app = create_app(Settings(app_env="test", app_name="PCRE"))
    spec = app.openapi()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OpenAPI escrito en {args.out} ({len(spec.get('paths', {}))} rutas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
