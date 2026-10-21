"""
Audit: how often do different Shorts end up with the same stock clip?

Replays the clip choice WITHOUT downloading anything, for (a) every Short already
prepared for TikTok (the public manifest) and (b) the first Shorts of the queue,
under the old rule (best-ranked valid results) and the current one (seeded pick
among the best-ranked). Also prints the Pexels clip(s) chosen for the slugs given
as arguments, so a bad clip can be added to videos/blocked_clips.txt.

Env: PEXELS_API_KEY, R2_PUBLIC_URL (to read tiktok/manifest.json).

Usage:
    python scripts/audit_clip_reuse.py [slug ...]
"""
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests

from fetch_clips import (
    MAX_DURATION_SECONDS, MIN_DURATION_SECONDS, candidates_for, load_blocklist, pick_video_file, search_clips,
)

ROOT = Path(__file__).resolve().parent.parent
VIDEOS = ROOT / "videos"
QUEUE_HEAD = 40
PAUSE_SECONDS = 0.4  # Pexels free tier: 200 requests / hour


def read_queue() -> list:
    return [s.strip() for s in (VIDEOS / "shorts_queue.txt").read_text().splitlines() if s.strip()]


def manifest_slugs() -> list:
    url = os.environ["R2_PUBLIC_URL"].rstrip("/") + "/tiktok/manifest.json"
    return [e["slug"] for e in requests.get(url, timeout=30).json()]


def old_choice(results: list, count: int) -> list:
    """The previous rule, exactly: first results that last 3-25 s and have an HD file."""
    return [
        v for v in results
        if MIN_DURATION_SECONDS <= v["duration"] <= MAX_DURATION_SECONDS and pick_video_file(v)
    ][:count]


def main(report_slugs: list):
    api_key = os.environ["PEXELS_API_KEY"]
    blocked = load_blocklist()
    slugs = list(dict.fromkeys(manifest_slugs() + read_queue()[:QUEUE_HEAD] + report_slugs))
    cache = {}

    def results_for(keyword):
        if keyword not in cache:
            cache[keyword] = search_clips(keyword, api_key)
            time.sleep(PAUSE_SECONDS)
        return cache[keyword]

    users = {"old": defaultdict(list), "new": defaultdict(list)}
    for slug in slugs:
        meta_path = VIDEOS / slug / "meta.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        keyword = meta["keywords"][0]  # the first keyword supplies every clip while it has enough results
        count = meta.get("numClips", 2)
        results = results_for(keyword)
        picks = {
            "old": old_choice(results, count),
            "new": candidates_for(slug, keyword, results, blocked)[:count],
        }
        for mode, videos in picks.items():
            for v in videos:
                users[mode][v["id"]].append(slug)
        if slug in report_slugs:
            for mode, videos in picks.items():
                for v in videos:
                    print(f"[{slug}] {mode}: pexels id {v['id']}  {v.get('url')}")

    print(f"\nShorts audited: {len(slugs)}")
    for mode in ("old", "new"):
        shared = {i: s for i, s in users[mode].items() if len(s) > 1}
        videos_sharing = {slug for s in shared.values() for slug in s}
        print(f"\n== {mode}: {len(users[mode])} distinct clips, {len(shared)} clips used by 2+ Shorts, "
              f"{len(videos_sharing)} Shorts affected")
        for clip_id, owners in sorted(shared.items(), key=lambda kv: -len(kv[1]))[:12]:
            print(f"  clip {clip_id}: {len(owners)} Shorts -> {', '.join(owners[:6])}")


if __name__ == "__main__":
    main(sys.argv[1:])
