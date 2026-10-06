"""Utilidades de base de datos para scripts (sin psql): vaciar, cargar SQL y contar filas.

Uso (desde apps/backend): `uv run python ../../scripts/dev/dbtool.py <comando> [args]`.
Lee `DATABASE_URL` del entorno. `reset` borra todo el esquema `public`: úsalo solo con
bases desechables (`pcre_migcheck`, `pcre_test`) o con tu base de desarrollo.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg


def _url() -> str:
    url = os.environ["DATABASE_URL"]
    return url.replace("postgresql+psycopg://", "postgresql://", 1).replace(
        "postgres://", "postgresql://", 1
    )


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    cmd, *args = argv
    with psycopg.connect(_url(), autocommit=True) as conn:
        if cmd == "reset":
            conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
            conn.execute("CREATE SCHEMA public")
            print("esquema public vaciado")
        elif cmd == "load-sql":
            sql = Path(args[0]).read_text(encoding="utf-8")
            conn.execute(sql.encode())
            print(f"cargado {args[0]}")
        elif cmd == "count":
            row = conn.execute(f'SELECT count(*) FROM "{args[0]}"').fetchone()  # noqa: S608
            print(row[0] if row else 0)
        elif cmd == "query":
            row = conn.execute(args[0].encode()).fetchone()
            print(row[0] if row else "")
        else:
            print(f"comando desconocido: {cmd}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
