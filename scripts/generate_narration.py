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

VOICE = "en-US-GuyNeural"


async def synthesize(text: str, out_path: Path):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(str(out_path))


def main(video_dir: str):
    video_dir = Path(video_dir)
    narration = video_dir / "narration.mp3"

    if narration.exists():
        print(f"{narration} already present, skipping generation")
        return

    meta = json.loads((video_dir / "meta.json").read_text())
    script = meta.get("script")
    if not script:
        raise SystemExit('meta.json is missing a "script" field for narration')

    asyncio.run(synthesize(script, narration))
    print(f"\nDone: {narration}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/generate_narration.py videos/<slug>")
    main(sys.argv[1])
