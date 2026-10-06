"""Importa todos los modelos para que la metadata esté completa (Alembic y pruebas).

Las tablas legadas viven aquí también: si salieran de la metadata, `alembic check`
propondría borrarlas (plan MVP-01, D10).
"""

from __future__ import annotations

import importlib

MODEL_MODULES = (
    "app.modules.legacy.models",
    "app.modules.identity.models",
)


def import_all_models() -> None:
    for name in MODEL_MODULES:
        importlib.import_module(name)
