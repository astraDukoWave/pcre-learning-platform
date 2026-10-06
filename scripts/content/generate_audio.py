"""Genera el audio de una unidad con TTS (ADR-12, contrato §11).

Uso (desde apps/backend):
  uv run python ../../scripts/content/generate_audio.py --unit u1 --dry-run
  uv run python ../../scripts/content/generate_audio.py --unit u1 --max-chars 20000

- `--dry-run` cuenta caracteres y estima el costo sin red ni llaves; sale con 2 si el
  conteo supera `--max-chars`.
- Sin `--dry-run` exige `DEEPGRAM_API_KEY` (solo existe en el environment `content-audio`
  del workflow aprobado) y aborta si el conteo pasa de `--max-chars`.
- Escribe `<sha8>-<id>.mp3` por entrada pendiente o con guion cambiado y actualiza el
  manifiesto (archivo, sha256, script_hash, voces, proveedor, modelo, fecha). La revisión
  (`reviewed_by`) la hace una persona después.
- Escribe un resumen JSON en `--summary` para el resumen del run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "backend"))

from app.modules.content.ports import SpeechSegment, TextToSpeech  # noqa: E402
from app.modules.content.schema import AudioEntry, AudioManifest, script_hash  # noqa: E402

PRICE_PER_1000_CHARS_USD = 0.030  # Aura-2, deepgram.com/pricing (5 oct 2026; reconfirmar en G2)
DEFAULT_VOICES = {
    "Narrator": "aura-2-thalia-en",
    "A": "aura-2-apollo-en",
    "B": "aura-2-helena-en",
    "C": "aura-2-arcas-en",
}


def pending_entries(manifest: AudioManifest, unit: str) -> list[AudioEntry]:
    """Entradas de la unidad sin archivo o con un guion distinto del generado."""
    prefix = f"{unit}-"
    return [
        e
        for e in manifest.audio
        if e.id.startswith(prefix) and (not e.file or e.script_hash != script_hash(e))
    ]


def count_chars(entries: list[AudioEntry]) -> int:
    return sum(len(line.text) for e in entries for line in e.script)


def estimate_usd(chars: int) -> float:
    return round(chars / 1000 * PRICE_PER_1000_CHARS_USD, 4)


def _silence(ms: int) -> bytes:
    """Silencio MP3 con ffmpeg si está disponible (pausas marcadas del guion)."""
    ffmpeg = shutil.which("ffmpeg")
    if ms <= 0 or ffmpeg is None:
        return b""
    with tempfile.NamedTemporaryFile(suffix=".mp3") as tmp:
        args = ["-loglevel", "error", "-y", "-f", "lavfi", "-t", f"{ms / 1000:.2f}"]
        args += ["-i", "anullsrc=r=24000:cl=mono", "-ac", "1", "-b:a", "48k", tmp.name]
        subprocess.run([ffmpeg, *args], check=True)  # noqa: S603
        return Path(tmp.name).read_bytes()


def synthesize_entry(entry: AudioEntry, tts: TextToSpeech) -> tuple[bytes, dict[str, str]]:
    voices = {**DEFAULT_VOICES, **entry.voices}
    parts: list[bytes] = []
    for line in entry.script:
        voice = voices.get(line.speaker, DEFAULT_VOICES["Narrator"])
        parts.append(
            tts.synthesize(SpeechSegment(line.speaker, voice, line.text, line.pause_after_ms))
        )
        parts.append(_silence(line.pause_after_ms))
    used = {
        line.speaker: voices.get(line.speaker, DEFAULT_VOICES["Narrator"]) for line in entry.script
    }
    return b"".join(parts), used


def run(
    path_dir: Path, unit: str, *, max_chars: int, dry_run: bool, tts: TextToSpeech | None
) -> dict[str, Any]:
    manifest_file = path_dir / "audio" / "manifest.yaml"
    raw = yaml.safe_load(manifest_file.read_text(encoding="utf-8")) or {"audio": []}
    manifest = AudioManifest.model_validate(raw)
    entries = pending_entries(manifest, unit)
    chars = count_chars(entries)
    summary: dict[str, Any] = {
        "unit": unit,
        "entries": [e.id for e in entries],
        "characters": chars,
        "estimated_usd": estimate_usd(chars),
        "max_chars": max_chars,
        "within_limit": chars <= max_chars,
        "dry_run": dry_run,
        "generated": [],
    }
    if dry_run or not entries:
        return summary
    if chars > max_chars:
        raise SystemExit(
            f"error: {chars} caracteres superan el tope de {max_chars}; no se generó nada"
        )
    if tts is None:
        raise SystemExit("error: falta el proveedor de TTS")
    now = datetime.now(UTC).isoformat(timespec="seconds")
    updated: dict[str, dict[str, Any]] = {}
    for entry in entries:
        audio, voices = synthesize_entry(entry, tts)
        digest = hashlib.sha256(audio).hexdigest()
        name = f"{script_hash(entry)[:8]}-{entry.id}.mp3"
        (path_dir / "audio" / name).write_bytes(audio)
        updated[entry.id] = {
            "file": name,
            "sha256": digest,
            "script_hash": script_hash(entry),
            "voices": voices,
            "provider": tts.provider,
            "model": tts.model,
            "generated_at": now,
            "reviewed_by": None,
            "reviewed_at": None,
        }
        summary["generated"].append(name)
    for item in raw["audio"]:
        if item["id"] in updated:
            item.update(updated[item["id"]])
    header = "".join(
        line + "\n"
        for line in manifest_file.read_text(encoding="utf-8").splitlines()
        if line.startswith("#")
    )
    manifest_file.write_text(
        header + yaml.safe_dump(raw, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit", required=True, help="prefijo de unidad, p. ej. u1")
    parser.add_argument("--max-chars", type=int, default=20000)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--path-dir", type=Path, default=ROOT / "content" / "toefl-ibt-2026-b1-b2")
    parser.add_argument("--summary", type=Path, default=None)
    args = parser.parse_args(argv)
    tts: TextToSpeech | None = None
    if not args.dry_run:
        from app.modules.content.adapters.deepgram_tts import DeepgramTextToSpeech

        tts = DeepgramTextToSpeech(os.environ.get("DEEPGRAM_API_KEY", ""))
    summary = run(args.path_dir, args.unit, max_chars=args.max_chars, dry_run=args.dry_run, tts=tts)
    text = json.dumps(summary, ensure_ascii=False, indent=2)
    print(text)
    if args.summary:
        args.summary.write_text(text, encoding="utf-8")
    if not summary["within_limit"]:
        print(f"error: el conteo supera --max-chars={args.max_chars}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
