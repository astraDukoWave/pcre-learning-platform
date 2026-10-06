"""Registro de los datos del alumno (REQ-06).

Toda tabla con una columna que apunte a `users.id` se registra aquí con sus reglas de
exportación y borrado. `tests/identity/test_data_registry.py` recorre la metadata y falla
si una tabla con datos del alumno no está registrada: así ningún módulo posterior olvida
sus datos al exportar o borrar una cuenta.

El borrado es siempre en cascada (`ON DELETE CASCADE` hacia `users`, desde
`identity_v1`); la prueba de borrado comprueba que no queda ninguna fila del usuario.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UserDataTable:
    table: str
    # Columnas que apuntan al usuario. La primera es la que define "sus" filas al exportar.
    user_columns: tuple[str, ...]
    export: bool
    exclude_columns: tuple[str, ...] = ()
    note: str = ""


REGISTRY: dict[str, UserDataTable] = {}


def register(entry: UserDataTable) -> None:
    REGISTRY[entry.table] = entry


register(
    UserDataTable(
        "users",
        ("id",),
        export=True,
        exclude_columns=("password_hash",),
        note="perfil, meta y consentimiento",
    )
)
register(
    UserDataTable(
        "auth_sessions",
        ("user_id",),
        export=True,
        exclude_columns=("token_hash", "csrf_hash"),
        note="sesiones (sin tokens)",
    )
)
register(
    UserDataTable(
        "invitations",
        ("consumed_user_id", "created_by"),
        export=False,
        note=(
            "metadatos de acceso administrados por el equipo; el email ya va en el perfil. "
            "Al borrar la cuenta se borran también las invitaciones con su email."
        ),
    )
)
register(
    UserDataTable(
        "password_reset_tokens",
        ("user_id", "created_by"),
        export=False,
        note="tokens de un uso; sin valor para el alumno",
    )
)
