"""Toda tabla con datos del alumno está registrada (REQ-06; plan CS-03)."""

from __future__ import annotations

from app.db.base import Base
from app.db.registry import import_all_models
from app.modules.identity.data_registry import REGISTRY


def _user_columns() -> dict[str, set[str]]:
    import_all_models()
    found: dict[str, set[str]] = {}
    for name, table in Base.metadata.tables.items():
        for column in table.columns:
            for fk in column.foreign_keys:
                if fk.column.table.name == "users" and fk.column.name == "id":
                    found.setdefault(name, set()).add(column.name)
            if column.name == "user_id":
                found.setdefault(name, set()).add("user_id")
    return found


def test_every_table_with_user_data_is_registered() -> None:
    missing = []
    for table, columns in _user_columns().items():
        entry = REGISTRY.get(table)
        if entry is None or not columns <= set(entry.user_columns):
            missing.append(f"{table}: {sorted(columns)}")
    assert not missing, "tablas con datos del alumno sin registrar: " + ", ".join(missing)
    assert "users" in REGISTRY


def test_every_fk_to_users_cascades() -> None:
    import_all_models()
    for name, table in Base.metadata.tables.items():
        for column in table.columns:
            for fk in column.foreign_keys:
                if fk.column.table.name == "users":
                    assert fk.ondelete == "CASCADE", f"{name}.{column.name} sin ON DELETE CASCADE"


def test_registry_points_at_real_tables() -> None:
    import_all_models()
    for name, entry in REGISTRY.items():
        table = Base.metadata.tables[name]
        for column in entry.user_columns + entry.exclude_columns:
            assert column in table.c, f"{name}.{column} no existe"
