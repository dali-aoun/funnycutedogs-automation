"""
Uploads videos/<slug>/reel.mp4 (the <60s vertical cut) to YouTube as a
Short, using the metadata in videos/<slug>/meta.json. "#shorts" and
"#short" are added to the title, description and tags — that's what makes
YouTube reliably classify and shelf a sub-60s vertical upload as a Short.

Usage:
    python scripts/upload_short_to_youtube.py videos/zoomies
"""
import json
import sys
from pathlib import Path

from youtube_lib import post_comment, upload_video

SHORTS_HASHTAGS = "#shorts #short"
PIN_COMMENT_TEXT = (
    "🔗 Full breakdown + the training program I mentioned: link in the description!\n"
    "🐾 New dog Shorts daily — subscribe so you don't miss the next one."
)


def main(video_dir: str):
    video_dir = Path(video_dir)
    reel = video_dir / "reel.mp4"

    if not reel.exists():
        raise SystemExit(f"Missing rendered short: {reel} (run assemble_reel.py first)")
    meta = json.loads((video_dir / "meta.json").read_text())

    title = f"{meta['title']} {SHORTS_HASHTAGS}"
    description = f"{meta['description']}\n\n{SHORTS_HASHTAGS}"
    tags = meta.get("tags", []) + ["shorts", "short"]

    video_id = upload_video(
        reel,
        title,
        description,
        tags,
        meta.get("privacyStatus", "public"),
    )
    print(f"\nShort upload complete: https://youtube.com/shorts/{video_id}")

    try:
        post_comment(video_id, PIN_COMMENT_TEXT)
        print("Posted link comment")
    except Exception as e:
        print(f"Could not post comment: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/upload_short_to_youtube.py videos/<slug>")
    main(sys.argv[1])
