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
register(
    UserDataTable(
        "content_reports",
        ("user_id",),
        export=True,
        note="reportes de contenido enviados por el alumno",
    )
)
register(UserDataTable("enrollments", ("user_id",), export=True, note="inscripción a la ruta"))
register(
    UserDataTable(
        "lesson_progress", ("user_id",), export=True, note="progreso por lección y revisión fijada"
    )
)
register(UserDataTable("served_aids", ("user_id",), export=True, note="ayudas servidas"))
register(
    UserDataTable("attempts", ("user_id",), export=True, note="intentos: respuestas y resultados")
)
register(
    UserDataTable(
        "idempotency_records",
        ("user_id",),
        export=False,
        note="registro técnico de reintentos; sin valor para el alumno",
    )
)
register(
    UserDataTable(
        "review_schedule", ("user_id",), export=True, note="repasos programados por objetivo"
    )
)
register(
    UserDataTable(
        "assessment_runs",
        ("user_id",),
        export=True,
        note=(
            "corridas de comprobación con su resumen por objetivo. Sus respuestas guardadas "
            "(`assessment_answers`) se borran en cascada con la corrida; al enviar se vuelven "
            "intentos, que sí se exportan."
        ),
    )
)
register(
    UserDataTable(
        "user_feedback", ("user_id",), export=True, note="valoraciones y comentarios del producto"
    )
)
register(
    UserDataTable(
        "product_events",
        ("user_id",),
        export=True,
        note="eventos de producto (lista cerrada de REQ-16; solo ids y enumerados)",
    )
)
