"""
Adds "Related videos" links to the descriptions of already-published videos that
cover the same topic (internal linking: viewers who find one video through search
get pointed to the others, and each video's description links the rest).

Groups live in videos/crosslinks.json: a list of groups, each a list of EXACT video
titles. Every published video of a group gets the URLs of the other published
videos of that group. Safe to re-run: URLs already present are never added twice.

Auth: the same YOUTUBE_* environment variables as the uploaders.

Usage:
    python scripts/cross_link_videos.py [--dry-run]
"""
import json
import sys
from pathlib import Path

from googleapiclient.discovery import build

from youtube_lib import get_credentials, uploads_by_title

ROOT = Path(__file__).resolve().parent.parent
GROUPS_FILE = ROOT / "videos" / "crosslinks.json"
MARKER = "▶ Related videos:"


def add_related_block(description: str, related: list) -> str:
    """Insert `related` [(title, url)] into `description`, skipping URLs already there.
    The block goes after the first paragraph, so the opening hook stays first in
    search results; if a block already exists, new items are appended to it."""
    fresh = [(t, u) for t, u in related if u not in description]
    if not fresh:
        return description
    lines = [f"{t}\n{u}" for t, u in fresh]

    if MARKER in description:
        head, tail = description.split(MARKER, 1)
        first_line, _, rest = tail.partition("\n")
        return f"{head}{MARKER}{first_line}\n" + "\n".join(lines) + ("\n" + rest if rest else "")

    block = MARKER + "\n" + "\n".join(lines)
    head, sep, tail = description.partition("\n\n")
    if not sep:
        return f"{description}\n\n{block}"
    return f"{head}\n\n{block}\n\n{tail}"


def main(dry_run: bool):
    groups = json.loads(GROUPS_FILE.read_text(encoding="utf-8"))
    youtube = build("youtube", "v3", credentials=get_credentials())
    ids = uploads_by_title(youtube)

    changed = 0
    for group in groups:
        found = {title: ids[title] for title in group if title in ids}
        for title in group:
            if title not in found:
                print(f"SKIP (not published yet): {title}")
        for title, video_id in found.items():
            related = [(t, f"https://youtu.be/{i}") for t, i in found.items() if t != title]
            snippet = youtube.videos().list(part="snippet", id=video_id).execute()["items"][0]["snippet"]
            updated = add_related_block(snippet["description"], related)
            if updated == snippet["description"]:
                print(f"OK (already linked): {title}")
                continue
            changed += 1
            print(f"{'WOULD UPDATE' if dry_run else 'UPDATING'}: {title} (+{len(updated) - len(snippet['description'])} chars)")
            if dry_run:
                continue
            body_snippet = {k: snippet[k] for k in ("title", "categoryId", "tags", "defaultLanguage") if k in snippet}
            body_snippet["description"] = updated
            youtube.videos().update(part="snippet", body={"id": video_id, "snippet": body_snippet}).execute()
    print(f"\n{changed} video(s) {'to update' if dry_run else 'updated'}")


if __name__ == "__main__":
    main("--dry-run" in sys.argv[1:])
