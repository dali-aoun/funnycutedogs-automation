"""
Uploads videos/<slug>/reel.mp4 (the <60s vertical cut) to YouTube as a
Short, using the metadata in videos/<slug>/meta.json. "#Shorts" is
appended to the title, which is what makes YouTube reliably classify and
shelf a sub-60s vertical upload as a Short.

Usage:
    python scripts/upload_short_to_youtube.py videos/zoomies
"""
import json
import sys
from pathlib import Path

from youtube_lib import upload_video


def main(video_dir: str):
    video_dir = Path(video_dir)
    reel = video_dir / "reel.mp4"

    if not reel.exists():
        raise SystemExit(f"Missing rendered short: {reel} (run assemble_reel.py first)")
    meta = json.loads((video_dir / "meta.json").read_text())

    title = f"{meta['title']} #Shorts"
    video_id = upload_video(
        reel,
        title,
        meta["description"],
        meta.get("tags", []),
        meta.get("privacyStatus", "public"),
    )
    print(f"\nShort upload complete: https://youtube.com/shorts/{video_id}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/upload_short_to_youtube.py videos/<slug>")
    main(sys.argv[1])
