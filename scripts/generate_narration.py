"""
Generates videos/<slug>/narration.mp3 from the "script" text in meta.json
using Microsoft Edge's free neural text-to-speech (no API key required).

Usage:
    python scripts/generate_narration.py videos/zoomies
"""
import asyncio
import json
import sys
from pathlib import Path

import edge_tts
from gtts import gTTS

VOICE = "en-US-GuyNeural"
EDGE_ATTEMPTS = 3


async def synthesize(text: str, out_path: Path):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(str(out_path))


def synthesize_with_fallback(text: str, out_path: Path):
    """Edge TTS is preferred (better voice) but Microsoft has rejected it before
    (403 on the websocket handshake, Oct 2026), which silently stopped every
    publish for two days. A plainer voice beats no video, so fall back to gTTS."""
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
