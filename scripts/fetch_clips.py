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
import random
import re
import shutil
import sys
from pathlib import Path

import requests

PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"
MIN_DURATION_SECONDS = 3
MAX_DURATION_SECONDS = 25
MIN_HD_WIDTH = 1280
MAX_PREFERRED_WIDTH = 1920
# Clips are picked at random (seeded by the video's slug, so a re-render gives the same
# footage) among the best-ranked results (one clip per keyword in turn, so two videos rarely share the same pair), instead of always the top ones: the old
# "first valid result" rule gave different Shorts the very same clip, and TikTok
# treats repeated footage as unoriginal content.
CANDIDATE_POOL = 20
SEARCH_PER_PAGE = 30
BLOCKLIST_FILE = Path(__file__).resolve().parent.parent / "videos" / "blocked_clips.txt"
# Pexels page URLs carry a description slug; never take a clip whose slug hints at adult content.
# A wider pool lets in off-topic footage (a "dog stretching" search returned a woman working out), so clips whose
# Pexels description names a dog are preferred; others are only used when too few dog clips exist.
DOG_URL_WORDS = re.compile(
    r"dog|puppy|puppies|pup|canine|corgi|labrador|retriever|husky|poodle|pug|bulldog|beagle|shepherd|pitbull|"
    r"pit-bull|chihuahua|terrier|dachshund|spaniel|collie|maltese|shih|doberman|rottweiler|boxer|schnauzer|samoyed|akita|malamute",
    re.I,
)
NOT_A_DOG_URL_WORDS = re.compile(r"yoga|downward|hot-?dog|workout|exercise|plush|stuffed|cartoon", re.I)
MIN_DOG_CLIPS = 3
UNSAFE_URL_WORDS = re.compile(r"mating|humping|breeding|copulat|sex|naked|nude|porn|erotic", re.I)


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


def load_blocklist() -> set:
    """Pexels video ids that must never be used (one per line, '#' comments allowed)."""
    if not BLOCKLIST_FILE.exists():
        return set()
    ids = set()
    for line in BLOCKLIST_FILE.read_text(encoding="utf-8").splitlines():
        token = line.split("#", 1)[0].strip()
        if token.isdigit():
            ids.add(int(token))
    return ids


def is_usable(video: dict, blocked: set) -> bool:
    return (
        video["id"] not in blocked
        and not UNSAFE_URL_WORDS.search(video.get("url", ""))
        and MIN_DURATION_SECONDS <= video["duration"] <= MAX_DURATION_SECONDS
    )


def candidates_for(slug: str, keyword: str, results: list, blocked: set) -> list:
    """Usable results for one keyword in this video's own (seeded) order."""
    usable = [v for v in results if is_usable(v, blocked)]
    dogs = [
        v for v in usable
        if DOG_URL_WORDS.search(v.get("url", "")) and not NOT_A_DOG_URL_WORDS.search(v.get("url", ""))
    ]
    pool = (dogs if len(dogs) >= MIN_DOG_CLIPS else usable)[:CANDIDATE_POOL]
    random.Random(f"{slug}|{keyword}").shuffle(pool)
    return pool


def search_clips(keyword: str, api_key: str, per_page: int = SEARCH_PER_PAGE) -> list:
    resp = requests.get(
        PEXELS_SEARCH_URL,
        headers={"Authorization": api_key},
        params={"query": keyword, "per_page": per_page, "orientation": "landscape"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("videos", [])


def choose_clips(slug: str, keywords: list, num_clips: int, results_for, blocked: set) -> list:
    """[(keyword, pexels video)] for one video: a clip per keyword in turn (seeded, HD only),
    never the same clip twice. `results_for(keyword)` returns the Pexels search results."""
    pools, exhausted, chosen, seen = {}, set(), [], set()
    turn = 0
    while len(chosen) < num_clips and len(exhausted) < len(keywords):
        i = turn % len(keywords)
        turn += 1
        if i in exhausted:
            continue
        if i not in pools:
            pools[i] = [
                v for v in candidates_for(slug, keywords[i], results_for(keywords[i]), blocked)
                if pick_video_file(v)
            ]
        while pools[i]:
            video = pools[i].pop(0)
            if video["id"] not in seen:
                seen.add(video["id"])
                chosen.append((keywords[i], video))
                break
        else:
            exhausted.add(i)
    return chosen


def main(video_dir: str):
    video_dir = Path(video_dir)
    clips_dir = video_dir / "clips"
    meta = json.loads((video_dir / "meta.json").read_text(encoding="utf-8"))

    # The creator's own footage (e.g. AI-generated clips of the recurring dog) lives in own_clips/, because
    # clips/ is git-ignored and CI only sees what is committed. It always wins over stock footage.
    own = sorted((video_dir / "own_clips").glob("*.mp4"))
    if own:
        clips_dir.mkdir(parents=True, exist_ok=True)
        for i, source in enumerate(own, start=1):
            shutil.copy(source, clips_dir / f"{i:02d}.mp4")
        print(f"Using {len(own)} own clip(s) from {video_dir / 'own_clips'}")
        return
    if meta.get("ownClips"):
        # Never fall back to stock footage for a video that is meant to show the creator's own dog.
        raise SystemExit(f"meta.json says ownClips but {video_dir / 'own_clips'} has no .mp4")

    if any(clips_dir.glob("*.mp4")):
        print(f"Clips already present in {clips_dir}, skipping fetch")
        return

    keywords = meta.get("keywords")
    num_clips = meta.get("numClips", 8)
    if not keywords:
        raise SystemExit('meta.json is missing a "keywords" list for clip sourcing')

    api_key = os.environ["PEXELS_API_KEY"]
    clips_dir.mkdir(parents=True, exist_ok=True)

    searches = {}

    def results_for(keyword):
        if keyword not in searches:
            searches[keyword] = search_clips(keyword, api_key)
        return searches[keyword]

    chosen = []
    downloaded = 0
    for keyword, video in choose_clips(video_dir.name, keywords, num_clips, results_for, load_blocklist()):
        file = pick_video_file(video)
        downloaded += 1
        chosen.append({"id": video["id"], "url": video.get("url"), "keyword": keyword})
        dest = clips_dir / f"{downloaded:02d}.mp4"
        print(f"Downloading clip {downloaded} ({keyword}, {file['width']}x{file['height']}): {file['link']}")
        r = requests.get(file["link"], timeout=60)
        r.raise_for_status()
        dest.write_bytes(r.content)

    (clips_dir / "clips.json").write_text(json.dumps(chosen, indent=1), encoding="utf-8")
    if downloaded == 0:
        raise SystemExit("No HD clips downloaded — check keywords or PEXELS_API_KEY")
    print(f"\nDownloaded {downloaded} clips to {clips_dir}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/fetch_clips.py videos/<slug>")
    main(sys.argv[1])
