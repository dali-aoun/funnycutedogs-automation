"""
Builds ready-to-paste TikTok captions (title + description + hashtags) for
the Shorts, from each videos/<slug>/meta.json. The TikTok inbox-upload API
cannot set a caption, so the creator pastes it in the app before publishing.

Prints JSON: {"recent": [...], "upcoming": [...]} where "recent" are the
latest Shorts already published (newest first) and "upcoming" follow the
queue order.

Usage:
    python scripts/tiktok_captions.py > captions.json
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIDEOS = ROOT / "videos"
BASE_HASHTAGS = ["#dogsoftiktok", "#funnydogs", "#dogbehavior", "#fyp", "#petsoftiktok"]
GENERIC_TAGS = {"dog facts", "dog behavior", "funny dogs", "cute dogs", "shorts", "short"}
MAX_TOPIC_HASHTAGS = 2
RECENT_COUNT = 6


def hashtag(tag: str) -> str:
    return "#" + re.sub(r"[^a-z0-9]", "", tag.lower())


def build_caption(meta: dict) -> dict:
    title = meta["title"]
    one_liner = meta["description"].split("\n", 1)[0].strip()
    topical = [t for t in meta.get("tags", []) if t.lower() not in GENERIC_TAGS]
    topic_tags = [hashtag(t) for t in topical[:MAX_TOPIC_HASHTAGS]]
    hashtags = BASE_HASHTAGS + topic_tags
    caption = f"{title} \U0001F43E\n\n{one_liner}\n\nFollow for daily dog clips \U0001F436\n\n{' '.join(hashtags)}"
    return {
        "title": title,
        "description": one_liner,
        "hashtags": " ".join(hashtags),
        "caption": caption,
        "hook": meta.get("hookText", ""),
    }


def load(slug: str):
    path = VIDEOS / slug / "meta.json"
    if not path.exists():
        return None
    entry = build_caption(json.loads(path.read_text(encoding="utf-8")))
    entry["slug"] = slug
    return entry


def recent_published_slugs() -> list:
    out = subprocess.run(
        ["git", "log", "--grep=dequeue short-", "-n", str(RECENT_COUNT), "--format=%s"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return [m.group(1) for m in re.finditer(r"dequeue (short-[\w-]+)", out)]


def main():
    queue = [s.strip() for s in (VIDEOS / "shorts_queue.txt").read_text().splitlines() if s.strip()]
    recent = [e for e in map(load, recent_published_slugs()) if e]
    upcoming = [e for e in map(load, queue) if e]
    json.dump({"recent": recent, "upcoming": upcoming}, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
