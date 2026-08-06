"""
Sources royalty-free dog video clips from the Pexels API into
videos/<slug>/clips/, based on the "keywords" list in meta.json. Only
downloads clips at 720p (HD) or above — sub-HD files are skipped entirely.

This replaces manual clip curation: Pexels footage is licensed for free
commercial reuse with no attribution required, so this also removes the
copyright risk of downloading/reposting other creators' videos.

Auth: PEXELS_API_KEY environment variable (free key from pexels.com/api).

Usage:
    python scripts/fetch_clips.py videos/zoomies
"""
import json
import os
import sys
from pathlib import Path

import requests

PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"
MIN_DURATION_SECONDS = 3
MAX_DURATION_SECONDS = 25
MIN_HD_WIDTH = 1280
MAX_PREFERRED_WIDTH = 1920


def pick_video_file(video: dict):
    hd_files = [
        f for f in video.get("video_files", [])
        if f.get("file_type") == "video/mp4" and (f.get("width") or 0) >= MIN_HD_WIDTH
    ]
    if not hd_files:
        return None
    hd_files.sort(key=lambda f: f.get("width") or 0)
    capped = [f for f in hd_files if (f.get("width") or 0) <= MAX_PREFERRED_WIDTH]
    # Prefer the sharpest file within the HD-to-1080p range; if every HD
    # option is above that (e.g. only 4K is offered), fall back to the
    # smallest one available rather than downloading an oversized file.
    return capped[-1] if capped else hd_files[0]


def search_clips(keyword: str, api_key: str, per_page: int = 15) -> list:
    resp = requests.get(
        PEXELS_SEARCH_URL,
        headers={"Authorization": api_key},
        params={"query": keyword, "per_page": per_page, "orientation": "landscape"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("videos", [])


def main(video_dir: str):
    video_dir = Path(video_dir)
    clips_dir = video_dir / "clips"
    meta = json.loads((video_dir / "meta.json").read_text())

    if any(clips_dir.glob("*.mp4")):
        print(f"Clips already present in {clips_dir}, skipping fetch")
        return

    keywords = meta.get("keywords")
    num_clips = meta.get("numClips", 8)
    if not keywords:
        raise SystemExit('meta.json is missing a "keywords" list for clip sourcing')

    api_key = os.environ["PEXELS_API_KEY"]
    clips_dir.mkdir(parents=True, exist_ok=True)

    seen_ids = set()
    downloaded = 0
    for keyword in keywords:
        if downloaded >= num_clips:
            break
        for video in search_clips(keyword, api_key):
            if downloaded >= num_clips:
                break
            if video["id"] in seen_ids:
                continue
            if not (MIN_DURATION_SECONDS <= video["duration"] <= MAX_DURATION_SECONDS):
                continue
            file = pick_video_file(video)
            if not file:
                continue
            seen_ids.add(video["id"])
            downloaded += 1
            dest = clips_dir / f"{downloaded:02d}.mp4"
            print(f"Downloading clip {downloaded} ({keyword}, {file['width']}x{file['height']}): {file['link']}")
            r = requests.get(file["link"], timeout=60)
            r.raise_for_status()
            dest.write_bytes(r.content)

    if downloaded == 0:
        raise SystemExit("No HD clips downloaded — check keywords or PEXELS_API_KEY")
    print(f"\nDownloaded {downloaded} clips to {clips_dir}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/fetch_clips.py videos/<slug>")
    main(sys.argv[1])
