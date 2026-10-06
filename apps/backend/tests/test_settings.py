from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings, normalize_database_url

URL = "postgresql+psycopg://u:p@127.0.0.1:5432/db"


def make(**kwargs: object) -> Settings:
    return Settings(database_url=kwargs.pop("database_url", URL), **kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("postgres://u:p@h:5432/d", "postgresql+psycopg://u:p@h:5432/d"),
        ("postgresql://u:p@h/d", "postgresql+psycopg://u:p@h/d"),
        ("postgresql+psycopg://u:p@h/d", "postgresql+psycopg://u:p@h/d"),
    ],
)
def test_database_url_is_normalized(raw: str, expected: str) -> None:
    assert normalize_database_url(raw) == expected
    assert make(database_url=raw).database_url == expected


def test_defaults_match_the_spec() -> None:
    s = make(app_env="dev")
    assert s.app_name == "PCRE"
    assert s.session_absolute_days == 7
    assert s.session_idle_hours == 24
    assert s.invitation_ttl_hours == 72
    assert s.reset_ttl_hours == 24
    assert s.review_intervals == (24, 72, 168)
    assert s.test_clock_enabled is False


def test_prod_requires_app_origin() -> None:
    with pytest.raises(ValidationError, match="APP_ORIGIN"):
        make(app_env="prod")
    s = make(app_env="prod", app_origin="https://pcre.example.com/")
    assert s.app_origin == "https://pcre.example.com"
    assert s.allowed_origins == ("https://pcre.example.com",)


def test_prod_refuses_test_clock() -> None:
    with pytest.raises(ValidationError, match="TEST_CLOCK_ENABLED"):
        make(app_env="prod", app_origin="https://x.example.com", test_clock_enabled=True)


def test_test_clock_only_active_in_test_env() -> None:
    assert make(app_env="test", test_clock_enabled=True).test_clock_active is True
    assert make(app_env="dev", test_clock_enabled=True).test_clock_active is False


def test_dev_origins_are_allowed_outside_prod() -> None:
    s = make(app_env="dev", app_origin="https://a.example.com")
    assert "https://a.example.com" in s.allowed_origins
    assert "http://localhost:5173" in s.allowed_origins


@pytest.mark.parametrize("raw", ["", "24,abc", "0,72", "-1"])
def test_invalid_review_intervals_are_rejected(raw: str) -> None:
    with pytest.raises(ValidationError):
        make(review_intervals_hours=raw)


def test_database_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings()
