"""
Uploads videos/<slug>/final.mp4 (the long-form, >60s video) to YouTube
using the metadata in videos/<slug>/meta.json.

Usage:
    python scripts/upload_to_youtube.py videos/zoomies
"""
import json
import sys
from pathlib import Path

from youtube_lib import post_comment, set_thumbnail, upload_video

PIN_COMMENT_TEXT = "🔗 Full breakdown + the training program I mentioned: link in the description!"


def main(video_dir: str):
    video_dir = Path(video_dir)
    final = video_dir / "final.mp4"
    thumbnail = video_dir / "thumbnail.jpg"

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

    if thumbnail.exists():
        try:
            set_thumbnail(video_id, thumbnail)
            print("Custom thumbnail set")
        except Exception as e:
            print(f"Could not set custom thumbnail (channel may need phone verification): {e}")

    try:
        post_comment(video_id, PIN_COMMENT_TEXT)
        print("Posted link comment")
    except Exception as e:
        print(f"Could not post comment: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/upload_to_youtube.py videos/<slug>")
    main(sys.argv[1])
