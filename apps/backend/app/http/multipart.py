"""Lectura de un formulario multipart solo en memoria (MVP-02 REQ-04).

`UploadFile` de Starlette guarda en un `SpooledTemporaryFile` que pasa a disco desde 1 MB;
el audio del alumno nunca debe tocar disco. Aquí se lee el cuerpo por trozos con el parser
de bajo nivel de `python-multipart` y cada parte queda en un `bytearray`. El tamaño ya lo
acota `BodyLimitMiddleware`; este lector además corta si una parte pasa de su límite.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from python_multipart.multipart import MultipartParser, parse_options_header
from starlette.requests import Request

from app.core.errors import AppError, ValidationFailed

MAX_FIELD_BYTES = 1024
MAX_PARTS = 8


class PayloadTooLarge(AppError):
    status_code = 413
    code = "payload_too_large"
    default_message = "El contenido enviado es demasiado grande."


@dataclass
class _Part:
    headers: dict[bytes, bytes] = field(default_factory=dict)
    data: bytearray = field(default_factory=bytearray)


@dataclass(frozen=True)
class UploadedFile:
    content: bytes
    content_type: str


@dataclass(frozen=True)
class MemoryForm:
    fields: dict[str, str]
    files: dict[str, UploadedFile]


async def read_memory_form(request: Request, *, max_file_bytes: int) -> MemoryForm:
    content_type, params = parse_options_header(request.headers.get("content-type", ""))
    boundary = params.get(b"boundary")
    if content_type != b"multipart/form-data" or not boundary:
        raise ValidationFailed(
            "Envía el audio como multipart/form-data.", code="multipart_required"
        )

    parts: list[_Part] = []
    header_field = bytearray()
    header_value = bytearray()

    def on_part_begin() -> None:
        if len(parts) >= MAX_PARTS:
            raise ValidationFailed("El formulario tiene demasiadas partes.", code="multipart_parts")
        parts.append(_Part())

    def on_part_data(data: bytes, start: int, end: int) -> None:
        part = parts[-1]
        part.data += data[start:end]
        limit = max_file_bytes if b"filename" in _disposition(part) else MAX_FIELD_BYTES
        if len(part.data) > limit:
            raise PayloadTooLarge()

    def on_header_field(data: bytes, start: int, end: int) -> None:
        header_field.extend(data[start:end])

    def on_header_value(data: bytes, start: int, end: int) -> None:
        header_value.extend(data[start:end])

    def on_header_end() -> None:
        parts[-1].headers[bytes(header_field).lower()] = bytes(header_value)
        header_field.clear()
        header_value.clear()

    parser = MultipartParser(
        boundary,
        {
            "on_part_begin": on_part_begin,
            "on_part_data": on_part_data,
            "on_header_field": on_header_field,
            "on_header_value": on_header_value,
            "on_header_end": on_header_end,
        },
    )
    async for chunk in request.stream():
        parser.write(chunk)
    parser.finalize()

    fields: dict[str, str] = {}
    files: dict[str, UploadedFile] = {}
    for part in parts:
        params = _disposition(part)
        name = params.get(b"name", b"").decode("utf-8", errors="replace")
        if not name:
            continue
        if b"filename" in params:
            files[name] = UploadedFile(
                content=bytes(part.data),
                content_type=part.headers.get(b"content-type", b"").decode("latin-1"),
            )
        else:
            fields[name] = part.data.decode("utf-8", errors="replace")
    return MemoryForm(fields=fields, files=files)


def _disposition(part: _Part) -> dict[bytes, bytes]:
    _, params = parse_options_header(part.headers.get(b"content-disposition", b""))
    return params
