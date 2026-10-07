"""AC-06 (parte pura): comparación de la repetición con fixtures, límites del audio y costo;
adaptador de Deepgram Nova-3 por REST con un transporte simulado (sin red ni llave real)."""

from __future__ import annotations

import threading
import time
from typing import Any

import httpx
import pytest

from app.modules.coaching.stt import domain
from app.modules.coaching.stt.adapters.deepgram import LISTEN_URL, DeepgramSpeechToText
from app.modules.coaching.stt.adapters.fake import FakeSpeechToText
from app.modules.coaching.stt.ports import SttFailed, SttUnknown


@pytest.mark.parametrize(
    ("target", "heard", "recognized", "total", "missing"),
    [
        # Todo, con mayúsculas y puntuación distintas.
        ("I would like a table for two, please.", "i would like a table for two please", 8, 8, []),
        # Falta una palabra; una de más no descuenta las demás.
        (
            "I would like a table for two, please.",
            "I would like um table for two please",
            7,
            8,
            ["a"],
        ),
        # Palabras repetidas o tartamudeo.
        ("Could you tell me the price?", "could could you tell me the the price", 6, 6, []),
        # El objetivo declara la contracción: «I'm» y «I am» valen igual, y cuenta una palabra.
        ("I'm a designer at a small studio.", "I am a designer at a small studio", 7, 7, []),
        ("I'm a designer at a small studio.", "I'm a designer at small studio", 6, 7, ["a"]),
        # Sin contracción en el objetivo, la forma contraída no cuenta.
        ("I am a nurse.", "I'm a nurse", 2, 4, ["I", "am"]),
        # Comillas tipográficas.
        ("We don’t open on Mondays.", "we don't open on mondays", 5, 5, []),
        # Nada reconocido.
        (
            "Which days do the classes meet?",
            "",
            0,
            6,
            ["Which", "days", "do", "the", "classes", "meet"],
        ),
    ],
)
def test_repeat_comparison_fixtures(
    target: str, heard: str, recognized: int, total: int, missing: list[str]
) -> None:
    result = domain.compare_repeat(target, heard)
    assert (result.recognized, result.total, list(result.missing)) == (recognized, total, missing)
    assert result.as_dict()["recognized_ratio"] == round(recognized / total, 4)


def test_audio_limits_and_cost() -> None:
    assert domain.check_audio("audio/webm;codecs=opus", 10, 1000) == "audio/webm"
    assert domain.check_audio("audio/mp4", domain.MAX_BYTES, 60_000) == "audio/mp4"
    for args, code in (
        (("audio/ogg", 10, 1000), "audio_type"),
        (("audio/webm", 0, 1000), "empty"),
        (("audio/webm", domain.MAX_BYTES + 1, 1000), "too_large"),
        (("audio/webm", 10, 0), "duration"),
        (("audio/webm", 10, 60_001), "too_long"),
    ):
        with pytest.raises(domain.AudioRejected) as rejected:
            domain.check_audio(*args)
        assert rejected.value.code == code
    assert not domain.too_long(60.4) and domain.too_long(60.6)
    # USD 0.0043/min: 60 s = 4 300 µUSD; se prorratea por segundo hacia arriba.
    assert domain.cost_microusd(60, 4300) == 4300 and domain.cost_microusd(0.2, 4300) == 72
    assert domain.max_cost_microusd(4300) >= domain.cost_microusd(60.5, 4300)


def deepgram(handler: Any, timeout_s: float = 15.0) -> DeepgramSpeechToText:
    return DeepgramSpeechToText(
        "clave-de-prueba",
        timeout_s=timeout_s,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_deepgram_request_shape_and_parsing() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url.copy_with(query=None))
        seen["params"] = dict(request.url.params)
        seen["auth"] = request.headers["authorization"]
        seen["type"] = request.headers["content-type"]
        seen["body"] = request.content
        return httpx.Response(
            200,
            json={
                "metadata": {"duration": 3.25},
                "results": {
                    "channels": [
                        {
                            "alternatives": [
                                {
                                    "transcript": "I would like a table.",
                                    "words": [
                                        {"word": "i", "punctuated_word": "I", "confidence": 0.99},
                                        {"word": "table", "confidence": 0.61},
                                    ],
                                }
                            ]
                        }
                    ]
                },
            },
        )

    result = deepgram(handler).transcribe(b"audio-en-memoria", "audio/webm;codecs=opus")
    assert seen["url"] == LISTEN_URL and seen["auth"] == "Token clave-de-prueba"
    assert seen["params"] == {
        "model": "nova-3",
        "language": "en",
        "smart_format": "true",
        "punctuate": "true",
    }
    assert seen["type"] == "audio/webm;codecs=opus" and seen["body"] == b"audio-en-memoria"
    assert result.text == "I would like a table." and result.duration_s == 3.25
    assert [(w.text, w.confidence) for w in result.words] == [("I", 0.99), ("table", 0.61)]


def test_deepgram_errors_map_to_failed_or_unknown() -> None:
    def status(code: int) -> Any:
        return lambda req: httpx.Response(code, json={"err_code": "x"})

    with pytest.raises(SttFailed) as failed:
        deepgram(status(400)).transcribe(b"a", "audio/webm")
    assert failed.value.code == "http_400"

    def connect(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin conexión", request=req)

    with pytest.raises(SttFailed) as not_sent:
        deepgram(connect).transcribe(b"a", "audio/webm")
    assert not_sent.value.code == "connect"

    def timeout(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("sin respuesta", request=req)

    with pytest.raises(SttUnknown) as unknown:
        deepgram(timeout).transcribe(b"a", "audio/webm")
    assert unknown.value.code == "timeout"

    def cut(req: httpx.Request) -> httpx.Response:
        raise httpx.RemoteProtocolError("cortada", request=req)

    with pytest.raises(SttUnknown):
        deepgram(cut).transcribe(b"a", "audio/webm")
    for body in (b"<html>proxy</html>", b"[1, 2]", b'{"results": [1]}'):
        with pytest.raises(SttUnknown) as unreadable:  # se procesó: pudo facturarse
            deepgram(lambda req, body=body: httpx.Response(200, content=body)).transcribe(
                b"a", "audio/webm"
            )
        assert unreadable.value.code == "invalid_response"
    with pytest.raises(ValueError):
        DeepgramSpeechToText("")


def test_deepgram_total_deadline() -> None:
    release, finished = threading.Event(), threading.Event()

    def slow(req: httpx.Request) -> httpx.Response:
        try:
            release.wait(5)
            raise httpx.ReadTimeout("tarde", request=req)
        finally:
            finished.set()

    started = time.perf_counter()
    with pytest.raises(SttUnknown) as late:
        deepgram(slow, timeout_s=0.2).transcribe(b"a", "audio/webm")
    assert late.value.code == "timeout" and time.perf_counter() - started < 1.0
    release.set()
    assert finished.wait(5)


def test_fake_speech_to_text_markers() -> None:
    fake = FakeSpeechToText()
    assert fake.transcribe(b"FAKE:hello there", "audio/webm").text == "hello there"
    assert fake.transcribe(b"real audio bytes", "audio/webm").text == fake.default_text
    assert fake.transcribe(b"FAKE:!long", "audio/webm").duration_s == 75.0
    with pytest.raises(SttFailed):
        fake.transcribe(b"FAKE:!failed", "audio/webm")
    with pytest.raises(SttUnknown):
        fake.transcribe(b"FAKE:!unknown", "audio/webm")
    assert fake.calls == 5
