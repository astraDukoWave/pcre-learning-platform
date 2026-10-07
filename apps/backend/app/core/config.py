"""Configuración de la app: solo variables de entorno (AGENTS.md, regla 7)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parents[1]


class ConfigError(RuntimeError):
    """La configuración no permite arrancar la app."""


def normalize_database_url(url: str) -> str:
    """Heroku entrega `postgres://…`; SQLAlchemy con psycopg 3 necesita otro esquema."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def database_url_from_env() -> str:
    """URL de la base para Alembic y scripts, sin exigir el resto de `Settings`."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise ConfigError("DATABASE_URL no está definida")
    return normalize_database_url(url)


def _parse_int_list(raw: str) -> tuple[int, ...]:
    values = tuple(int(part.strip()) for part in raw.split(",") if part.strip())
    if not values or any(v <= 0 for v in values):
        raise ValueError("debe ser una lista de enteros positivos separados por comas")
    return values


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    database_url: str
    app_env: Literal["dev", "test", "prod"] = "dev"
    app_name: str = "PCRE"
    app_origin: str | None = None
    dev_allowed_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"
    )
    log_level: str = "INFO"
    log_salt: str = ""
    session_absolute_days: int = 7
    session_idle_hours: int = 24
    invitation_ttl_hours: int = 72
    reset_ttl_hours: int = 24
    review_intervals_hours: str = "24,72,168"
    consent_version: str = "borrador-2026-10"
    privacy_contact_email: str = "privacidad@example.com"
    content_dir: Path = REPO_DIR / "content"
    media_dir: Path = REPO_DIR / "content" / "toefl-ibt-2026-b1-b2" / "audio"
    frontend_dist: Path = REPO_DIR / "apps" / "frontend" / "dist"
    test_clock_enabled: bool = False
    # MVP-02 (ADR-11): capacidades con costo. Apagadas por defecto y fail-closed: sin
    # presupuesto, precios y proveedor configurados responden 503 `capability_disabled`.
    ai_feedback_enabled: bool = False
    stt_enabled: bool = False
    voice_enabled: bool = False
    budget_global_monthly_microusd: int | None = Field(default=None, ge=0)
    budget_user_monthly_microusd: int | None = Field(default=None, ge=0)
    voice_max_minutes_per_user_month: int | None = Field(default=None, ge=0)
    gemini_price_input_per_mtok_microusd: int | None = Field(default=None, ge=0)
    gemini_price_output_per_mtok_microusd: int | None = Field(default=None, ge=0)
    stt_price_per_min_microusd: int = Field(default=4300, ge=0)
    voice_price_per_min_microusd: int = Field(default=75000, ge=0)
    # Evaluador del feedback: `fake` (doble determinista) solo fuera de producción.
    feedback_provider: Literal["gemini", "fake"] = "gemini"
    gemini_api_key: SecretStr | None = None
    gemini_model: str | None = None
    # Transcripción (REQ-04): Deepgram Nova-3; `fake` (doble determinista) solo fuera de prod.
    stt_provider: Literal["deepgram", "fake"] = "deepgram"
    deepgram_api_key: SecretStr | None = None
    # Coach de voz (REQ-05): Voice Agent de Deepgram. `fake` habla con el Deepgram falso de
    # las pruebas en `VOICE_AGENT_URL` (solo localhost y nunca en prod).
    voice_provider: Literal["deepgram", "fake"] = "deepgram"
    voice_agent_url: str | None = None
    voice_max_session_s: int = Field(default=300, ge=1, le=300)
    voice_listen_model: str = "nova-3"
    voice_think_provider: str = "open_ai"
    voice_think_model: str = "gpt-4o-mini"
    voice_speak_model: str = "aura-2-thalia-en"
    voice_output_sample_rate: int = Field(default=24_000, ge=8_000, le=48_000)

    @field_validator("database_url")
    @classmethod
    def _normalize_url(cls, value: str) -> str:
        return normalize_database_url(value.strip())

    @field_validator("review_intervals_hours")
    @classmethod
    def _check_intervals(cls, value: str) -> str:
        _parse_int_list(value)
        return value

    @field_validator("app_origin")
    @classmethod
    def _strip_origin(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return value.strip().rstrip("/")

    @model_validator(mode="after")
    def _guard_prod(self) -> Settings:
        if self.app_env == "prod":
            if not self.app_origin:
                raise ValueError("APP_ORIGIN es obligatoria con APP_ENV=prod")
            if self.test_clock_enabled:
                raise ValueError("TEST_CLOCK_ENABLED no se permite con APP_ENV=prod")
            if self.feedback_provider == "fake":
                raise ValueError("FEEDBACK_PROVIDER=fake no se permite con APP_ENV=prod")
            if self.stt_provider == "fake":
                raise ValueError("STT_PROVIDER=fake no se permite con APP_ENV=prod")
            if self.voice_provider == "fake" or self.voice_agent_url:
                raise ValueError("VOICE_PROVIDER=fake y VOICE_AGENT_URL no se permiten en prod")
        return self

    @property
    def review_intervals(self) -> tuple[int, ...]:
        return _parse_int_list(self.review_intervals_hours)

    @property
    def allowed_origins(self) -> tuple[str, ...]:
        origins: list[str] = [self.app_origin] if self.app_origin else []
        if self.app_env != "prod":
            origins += [o.strip().rstrip("/") for o in self.dev_allowed_origins.split(",")]
        return tuple(o for o in origins if o)

    @property
    def test_clock_active(self) -> bool:
        return self.app_env == "test" and self.test_clock_enabled


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # database_url llega del entorno
