"""Único punto de composición: construye adaptadores y servicios desde `Settings`."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Engine

from app.core.clock import Clock, OffsetClock, SystemClock
from app.core.config import Settings
from app.core.security import Passwords
from app.db.engine import create_db_engine
from app.db.session import make_sessionmaker
from app.db.uow import UnitOfWorkFactory
from app.modules.coaching.feedback.adapters.fake import FakeFeedbackEvaluator
from app.modules.coaching.feedback.adapters.gemini import GeminiFeedbackEvaluator
from app.modules.coaching.feedback.ports import FeedbackEvaluator
from app.modules.coaching.stt.adapters.deepgram import DeepgramSpeechToText
from app.modules.coaching.stt.adapters.fake import FakeSpeechToText
from app.modules.coaching.stt.ports import SpeechToText
from app.modules.identity.domain import SlidingWindowLimiter

# Login: 5 intentos por minuto y 20 por hora, por email y por IP (§7).
LOGIN_LIMITS = ((5, 60), (20, 3600))


@dataclass
class Container:
    settings: Settings
    uow: UnitOfWorkFactory
    clock: Clock
    engine: Engine | None = None
    passwords: Passwords = field(default_factory=Passwords)
    login_limiter: SlidingWindowLimiter = field(
        default_factory=lambda: SlidingWindowLimiter(LOGIN_LIMITS)
    )
    extras: dict[str, Any] = field(default_factory=dict)
    # Capacidades con costo (MVP-02) cuyo proveedor, real o doble, está configurado.
    ready_providers: frozenset[str] = frozenset()
    feedback_evaluator: FeedbackEvaluator | None = None
    speech_to_text: SpeechToText | None = None

    def provider_ready(self, capability: str) -> bool:
        return capability in self.ready_providers


def build_feedback_evaluator(settings: Settings) -> FeedbackEvaluator | None:
    """Gemini con llave y modelo configurados (G5); el doble solo fuera de producción."""
    if settings.feedback_provider == "fake":
        return FakeFeedbackEvaluator() if settings.app_env != "prod" else None
    if settings.gemini_api_key is not None and settings.gemini_model:
        return GeminiFeedbackEvaluator(
            settings.gemini_api_key.get_secret_value(), settings.gemini_model
        )
    return None


def build_speech_to_text(settings: Settings) -> SpeechToText | None:
    """Deepgram con llave configurada (G5); el doble solo fuera de producción."""
    if settings.stt_provider == "fake":
        return FakeSpeechToText() if settings.app_env != "prod" else None
    if settings.deepgram_api_key is not None:
        return DeepgramSpeechToText(settings.deepgram_api_key.get_secret_value())
    return None


def build_container(settings: Settings) -> Container:
    engine = create_db_engine(settings)
    clock: Clock = OffsetClock() if settings.test_clock_active else SystemClock()
    evaluator = build_feedback_evaluator(settings)
    stt = build_speech_to_text(settings)
    ready = {"ai_feedback"} if evaluator is not None else set()
    if stt is not None:
        ready.add("stt")
    return Container(
        settings=settings,
        uow=UnitOfWorkFactory(make_sessionmaker(engine)),
        clock=clock,
        engine=engine,
        feedback_evaluator=evaluator,
        speech_to_text=stt,
        ready_providers=frozenset(ready),
    )
