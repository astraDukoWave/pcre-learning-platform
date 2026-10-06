"""Metadata única de SQLAlchemy 2. Cada módulo declara sus modelos sobre esta base."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
