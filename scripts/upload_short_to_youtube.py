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

from youtube_lib import find_video_id_by_title, post_comment, upload_video

SHORTS_HASHTAGS = "#shorts #short"
MAX_TITLE_CHARS = 100
PIN_COMMENT_TEXT = (
    "🔗 Full breakdown + the training program I mentioned: link in the description!\n"
    "🐾 New dog Shorts daily — subscribe so you don't miss the next one."
)


def short_title(meta: dict) -> str:
    """A Short that advertises a long video leads with that video's exact question:
    on this channel, Shorts reach people through YouTube search (91% of Shorts views,
    ~0 from the Shorts feed), and the one titled like its long video got 3x the views
    of the teaser-titled ones. Stays under YouTube's 100-char limit with the hashtags."""
    promo = meta.get("promotesTitle")
    if not promo:
        return meta["title"]
    limit = MAX_TITLE_CHARS - len(SHORTS_HASHTAGS) - 1
    combined = f"{promo} | {meta['title']}"
    return combined if len(combined) <= limit else promo[:limit]


def promo_url(meta: dict):
    """Link to the long-form this Short advertises, if it is already published.
    YouTube lets Shorts descriptions and comments link to other YouTube videos."""
    title = meta.get("promotesTitle")
    if not title:
        return None
    try:
        video_id = find_video_id_by_title(title)
    except Exception as e:
        print(f"Could not look up the promoted video: {e}")
        return None
    return f"https://youtu.be/{video_id}" if video_id else None


def main(video_dir: str):
    video_dir = Path(video_dir)
    reel = video_dir / "reel.mp4"

    if not reel.exists():
        raise SystemExit(f"Missing rendered short: {reel} (run assemble_reel.py first)")
    meta = json.loads((video_dir / "meta.json").read_text())

    title = f"{short_title(meta)} {SHORTS_HASHTAGS}"
    link = promo_url(meta)
    promo = f"▶ Full video: {meta['promotesTitle']}\n{link}\n\n" if link else ""
    description = f"{promo}{meta['description']}\n\n{SHORTS_HASHTAGS}"
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
        post_comment(video_id, f"▶ Full video: {link}" if link else PIN_COMMENT_TEXT)
        print("Posted link comment")
    except Exception as e:
        print(f"Could not post comment: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/upload_short_to_youtube.py videos/<slug>")
    main(sys.argv[1])
