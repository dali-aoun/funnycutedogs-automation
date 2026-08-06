"""
Uploads videos/<slug>/final.mp4 (the long-form, >60s video) to YouTube
using the metadata in videos/<slug>/meta.json.

Usage:
    python scripts/upload_to_youtube.py videos/zoomies
"""
import json
import sys
from pathlib import Path

from youtube_lib import upload_video


def main(video_dir: str):
    video_dir = Path(video_dir)
    final = video_dir / "final.mp4"

    if not final.exists():
        raise SystemExit(f"Missing rendered video: {final}")
    meta = json.loads((video_dir / "meta.json").read_text())

    video_id = upload_video(
        final,
        meta["title"],
        meta["description"],
        meta.get("tags", []),
        meta.get("privacyStatus", "public"),
    )
    print(f"\nUpload complete: https://youtube.com/watch?v={video_id}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/upload_to_youtube.py videos/<slug>")
    main(sys.argv[1])
