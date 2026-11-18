"""
Generates videos/<slug>/narration.mp3 from the "script" text in meta.json.

Engines, in order:
  1. Kokoro (open weights, Apache 2.0, runs locally) -- only when TTS_ENGINE=kokoro.
  2. Microsoft Edge's free neural text-to-speech (no API key, but an unofficial service).
  3. gTTS, a plainer voice that beats publishing nothing.

Usage:
    python scripts/generate_narration.py videos/zoomies
"""
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import edge_tts
from gtts import gTTS

VOICE = "en-US-GuyNeural"
EDGE_ATTEMPTS = 3

# am_michael: best-graded American male English voice in Kokoro's VOICES.md (C+), and slower than am_adam,
# which suits explanations. Model files are fetched once into KOKORO_DIR.
KOKORO_VOICE = "am_michael"
KOKORO_BASE_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
KOKORO_MODEL, KOKORO_VOICES = "kokoro-v1.0.int8.onnx", "voices-v1.0.bin"
KOKORO_DIR = Path(os.environ.get("KOKORO_DIR", ".cache/kokoro"))


async def synthesize(text: str, out_path: Path):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(str(out_path))


def synthesize_kokoro(text: str, out_path: Path):
    import requests
    import soundfile
    from kokoro_onnx import Kokoro

    KOKORO_DIR.mkdir(parents=True, exist_ok=True)
    for name in (KOKORO_MODEL, KOKORO_VOICES):
        target = KOKORO_DIR / name
        if not target.exists():
            response = requests.get(f"{KOKORO_BASE_URL}/{name}", timeout=300)
            response.raise_for_status()
            target.write_bytes(response.content)

    engine = Kokoro(str(KOKORO_DIR / KOKORO_MODEL), str(KOKORO_DIR / KOKORO_VOICES))
    samples, rate = engine.create(text, voice=KOKORO_VOICE, speed=1.0, lang="en-us")
    wav_path = out_path.with_suffix(".wav")
    soundfile.write(str(wav_path), samples, rate)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(wav_path), "-b:a", "128k", str(out_path)], check=True)
    wav_path.unlink()


def synthesize_with_fallback(text: str, out_path: Path):
    """Edge TTS has been rejected by Microsoft before (403 on the websocket handshake, Oct 2026), which
    silently stopped every publish for two days, so every engine falls through to the next one."""
    if os.environ.get("TTS_ENGINE") == "kokoro":
        try:
            synthesize_kokoro(text, out_path)
            return
        except Exception as e:
            print(f"Kokoro failed, trying Edge TTS: {type(e).__name__}: {e}")
            out_path.unlink(missing_ok=True)

    last_error = None
    for attempt in range(1, EDGE_ATTEMPTS + 1):
        try:
            asyncio.run(synthesize(text, out_path))
            return
        except Exception as e:
            last_error = e
            print(f"Edge TTS attempt {attempt}/{EDGE_ATTEMPTS} failed: {type(e).__name__}: {e}")
    print(f"Falling back to gTTS after: {last_error}")
    gTTS(text=text, lang="en", tld="com").save(str(out_path))


def main(video_dir: str):
    video_dir = Path(video_dir)
    narration = video_dir / "narration.mp3"

    if narration.exists():
        print(f"{narration} already present, skipping generation")
        return

    meta = json.loads((video_dir / "meta.json").read_text(encoding="utf-8"))
    script = meta.get("script")
    if not script:
        raise SystemExit('meta.json is missing a "script" field for narration')

    synthesize_with_fallback(script, narration)
    print(f"\nDone: {narration}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/generate_narration.py videos/<slug>")
    main(sys.argv[1])
