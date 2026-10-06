"""`scripts/content/generate_audio.py` con el doble de TTS y el adaptador de Deepgram contra
un transporte simulado: ninguna prueba usa la red ni una llave real."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest
import yaml

from app.modules.content.adapters.deepgram_tts import DeepgramTextToSpeech
from app.modules.content.adapters.fake_tts import FakeTextToSpeech
from app.modules.content.ports import SpeechSegment

SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "content" / "generate_audio.py"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_audio", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ENTRIES: list[dict[str, Any]] = [
    {
        "id": "u1-l2-aviso",
        "script": [
            {"speaker": "Narrator", "text": "The library closes early today.", "pause_after_ms": 0}
        ],
    },
    {
        "id": "u1-l2-respuesta",
        "script": [
            {"speaker": "A", "text": "Could you help me?"},
            {"speaker": "B", "text": "Sure, what do you need?"},
        ],
        "voices": {"B": "aura-2-luna-en"},
    },
    {"id": "u2-l2-otro", "script": [{"speaker": "Narrator", "text": "Not this unit."}]},
]


def write_manifest(tmp_path: Path, entries: list[dict[str, Any]] = ENTRIES) -> Path:
    (tmp_path / "audio").mkdir(parents=True)
    (tmp_path / "audio" / "manifest.yaml").write_text(
        "# Cabecera que se conserva.\n" + yaml.safe_dump({"audio": entries}, sort_keys=False),
        encoding="utf-8",
    )
    return tmp_path


def test_dry_run_counts_characters_and_estimates_cost_without_a_provider(tmp_path: Path) -> None:
    gen = load_script()
    summary = gen.run(write_manifest(tmp_path), "u1", max_chars=1000, dry_run=True, tts=None)
    chars = len("The library closes early today.") + len("Could you help me?")
    chars += len("Sure, what do you need?")
    assert summary["entries"] == ["u1-l2-aviso", "u1-l2-respuesta"]
    assert summary["characters"] == chars
    assert summary["estimated_usd"] == round(chars / 1000 * 0.030, 4)
    assert summary["within_limit"] is True and summary["generated"] == []
    assert list((tmp_path / "audio").iterdir()) == [tmp_path / "audio" / "manifest.yaml"]


def test_dry_run_exits_2_over_the_limit(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    gen = load_script()
    write_manifest(tmp_path)
    code = gen.main(["--unit", "u1", "--dry-run", "--max-chars", "10", "--path-dir", str(tmp_path)])
    assert code == 2
    assert json.loads(capsys.readouterr().out)["within_limit"] is False


def test_generation_aborts_over_the_limit_before_calling_the_provider(tmp_path: Path) -> None:
    gen = load_script()
    fake = FakeTextToSpeech()
    with pytest.raises(SystemExit, match="superan el tope"):
        gen.run(write_manifest(tmp_path), "u1", max_chars=10, dry_run=False, tts=fake)
    assert fake.calls == []


def test_generation_writes_files_named_by_script_hash_and_updates_the_manifest(
    tmp_path: Path,
) -> None:
    gen = load_script()
    fake = FakeTextToSpeech()
    path_dir = write_manifest(tmp_path)
    summary = gen.run(path_dir, "u1", max_chars=1000, dry_run=False, tts=fake)
    assert [c.voice for c in fake.calls] == [
        "aura-2-thalia-en",
        "aura-2-apollo-en",
        "aura-2-luna-en",
    ]
    text = (path_dir / "audio" / "manifest.yaml").read_text(encoding="utf-8")
    assert text.startswith("# Cabecera que se conserva.\n")
    manifest = yaml.safe_load(text)["audio"]
    first = manifest[0]
    assert first["file"] == summary["generated"][0]
    assert (
        first["file"].endswith("-u1-l2-aviso.mp3") and first["file"][:8] == first["script_hash"][:8]
    )
    data = (path_dir / "audio" / first["file"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == first["sha256"]
    assert first["provider"] == "fake" and first["reviewed_by"] is None
    assert manifest[1]["voices"] == {"A": "aura-2-apollo-en", "B": "aura-2-luna-en"}
    assert "file" not in manifest[2]  # otra unidad
    # Sin cambios en el guion no hay nada pendiente; un guion editado vuelve a generarse.
    assert gen.run(path_dir, "u1", max_chars=1000, dry_run=True, tts=None)["entries"] == []
    raw = yaml.safe_load(text)
    raw["audio"][0]["script"][0]["text"] = "The library closes at noon today."
    (path_dir / "audio" / "manifest.yaml").write_text(yaml.safe_dump(raw), encoding="utf-8")
    assert gen.run(path_dir, "u1", max_chars=1000, dry_run=True, tts=None)["entries"] == [
        "u1-l2-aviso"
    ]


def test_fake_provider_audio_is_rejected_by_the_lint(tmp_path: Path) -> None:
    """El manifiesto exige proveedor real: lo generado con el doble no pasa el lint."""
    from app.modules.content.lint import lint_dir
    from tests.content.builder import write_content

    gen = load_script()

    def mutate(files: dict[str, Any]) -> None:
        files["audio/manifest.yaml"] = {"audio": [ENTRIES[0]]}

    root = write_content(tmp_path / "content", mutate)
    path_dir = next((root).iterdir())
    gen.run(path_dir, "u1", max_chars=1000, dry_run=False, tts=FakeTextToSpeech())
    issues = next(iter(lint_dir(root).values()))[1]
    assert any(i.code == "audio_provider" for i in issues)


def test_deepgram_adapter_sends_the_voice_and_returns_audio() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=b"ID3mp3", headers={"content-type": "audio/mpeg"})

    tts = DeepgramTextToSpeech(
        "placeholder", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    audio = tts.synthesize(SpeechSegment("A", "aura-2-apollo-en", "Hello there."))
    assert audio == b"ID3mp3"
    request = seen[0]
    assert request.url.host == "api.deepgram.com" and request.url.path == "/v1/speak"
    assert request.url.params["model"] == "aura-2-apollo-en"
    assert request.url.params["encoding"] == "mp3"
    assert request.headers["authorization"] == "Token placeholder"
    assert json.loads(request.content) == {"text": "Hello there."}


def test_deepgram_adapter_fails_on_errors_and_non_audio() -> None:
    def error(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"err_msg": "invalid credentials"})

    def html(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>", headers={"content-type": "text/html"})

    segment = SpeechSegment("A", "aura-2-apollo-en", "Hi.")
    with pytest.raises(httpx.HTTPStatusError):
        DeepgramTextToSpeech(
            "x", client=httpx.Client(transport=httpx.MockTransport(error))
        ).synthesize(segment)
    with pytest.raises(RuntimeError):
        DeepgramTextToSpeech(
            "x", client=httpx.Client(transport=httpx.MockTransport(html))
        ).synthesize(segment)
    with pytest.raises(ValueError, match="DEEPGRAM_API_KEY"):
        DeepgramTextToSpeech("")
