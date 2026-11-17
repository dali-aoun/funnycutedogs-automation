"""
Blocks a publish run early, before any download or upload, when videos/<slug>/meta.json
is incomplete or breaks a rule the channel has already been burned by.

A failing check leaves the slug at the front of its queue (the dequeue job only runs after a
successful publish), so fix the file and the next run retries it.

Usage:
    python scripts/check_meta.py videos/zoomies --kind long
    python scripts/check_meta.py videos/short-rex-rain --kind short
    python scripts/check_meta.py --queued        # every slug in both queues (used as a sanity run)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_TITLE_CHARS = 100
MIN_LONG_SCRIPT_WORDS = 120
MAX_SHORT_SCRIPT_WORDS = 30


def problems(video_dir: Path, kind: str) -> list:
    meta_path = video_dir / "meta.json"
    if not meta_path.exists():
        return [f"missing {meta_path}"]
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except ValueError as e:
        return [f"meta.json is not valid JSON ({e})"]

    found = [f"missing or empty '{k}'" for k in ("title", "description", "script") if not str(meta.get(k, "")).strip()]
    if len(meta.get("title", "")) > MAX_TITLE_CHARS:
        found.append(f"title is {len(meta['title'])} characters (YouTube allows {MAX_TITLE_CHARS})")

    words = len(str(meta.get("script", "")).split())
    if kind == "long" and 0 < words < MIN_LONG_SCRIPT_WORDS:
        found.append(f"long script has {words} words (< {MIN_LONG_SCRIPT_WORDS}, the video would end under 60 s)")
    if kind == "short" and words > MAX_SHORT_SCRIPT_WORDS:
        found.append(f"short script has {words} words (> {MAX_SHORT_SCRIPT_WORDS})")

    description = str(meta.get("description", "")).lower()
    if "/go/" in description and "affiliate" not in description:
        found.append("description has an affiliate link but no affiliate disclosure")
    if meta.get("aiGenerated") and "aigenerated" not in description:
        found.append("aiGenerated video without the #aigenerated disclosure in the description")

    if meta.get("ownClips"):
        if not list((video_dir / "own_clips").glob("*.mp4")):
            found.append("ownClips is set but own_clips/ has no .mp4")
    elif not meta.get("keywords"):
        found.append("no 'keywords' for stock clip sourcing")

    promotes = meta.get("promotes")
    if promotes and not meta.get("promotesTitle"):
        found.append("'promotes' is set without 'promotesTitle'")
    if promotes and not (ROOT / "videos" / promotes / "meta.json").exists():
        found.append(f"promotes '{promotes}' but videos/{promotes}/ does not exist")
    return found


def queued_slugs() -> list:
    out = []
    for queue, kind in (("queue.txt", "long"), ("shorts_queue.txt", "short")):
        path = ROOT / "videos" / queue
        if path.exists():
            out += [(line.strip(), kind) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return out


def main(argv: list) -> int:
    targets = queued_slugs() if argv == ["--queued"] else None
    if targets is None:
        if len(argv) != 3 or argv[1] != "--kind" or argv[2] not in ("long", "short"):
            raise SystemExit("Usage: python scripts/check_meta.py videos/<slug> --kind long|short  |  --queued")
        targets = [(Path(argv[0]).name, argv[2])]

    failed = 0
    for slug, kind in targets:
        for message in problems(ROOT / "videos" / slug, kind):
            failed += 1
            print(f"FAIL {slug}: {message}")
    print(f"{len(targets)} checked, {failed} problem(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
