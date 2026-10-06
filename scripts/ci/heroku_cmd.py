"""Imprime un comando de heroku.yml para que la CI arranque exactamente lo de producción.

Uso: `python scripts/ci/heroku_cmd.py web|release`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def main(which: str) -> int:
    data = yaml.safe_load((ROOT / "heroku.yml").read_text(encoding="utf-8"))
    if which == "web":
        print(data["run"]["web"])
    elif which == "release":
        print(" && ".join(data["release"]["command"]))
    else:
        print(f"uso: {sys.argv[0]} web|release", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ""))
