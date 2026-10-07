"""
Prepares the next N Shorts for manual TikTok posting, ahead of time.

TikTok cannot be posted to unattended, so the creator uploads by hand. To let
a whole week be scheduled in one sitting, this renders the next N queued
Shorts (the same videos YouTube and Instagram will publish) and archives each
one with its caption, so funnycutedogs.com/tiktok/ lists them in posting
order. It does NOT upload to YouTube or Instagram and does NOT touch the
queue; the daily workflow keeps publishing there on its own.

Videos already in the manifest are skipped, so running it twice never
duplicates work.

Env: PEXELS_API_KEY plus the R2_* variables used by archive_for_tiktok.py.

Usage:
    python scripts/prepare_tiktok_batch.py 14
"""
import os
import subprocess
import sys
from pathlib import Path

from archive_for_tiktok import REQUIRED_ENV, load_manifest, main as archive, r2_client

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
DEFAULT_COUNT = 14
RENDER_STEPS = ("fetch_clips.py", "generate_narration.py", "assemble_short.py")


def render(slug: str):
    video_dir = ROOT / "videos" / slug
    for step in RENDER_STEPS:
        subprocess.run([sys.executable, str(SCRIPTS / step), str(video_dir)], check=True)


def main(count: int):
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing or not os.environ.get("PEXELS_API_KEY"):
        raise SystemExit(f"Missing environment: {', '.join(missing) or 'PEXELS_API_KEY'}")

    queue = [s.strip() for s in (ROOT / "videos" / "shorts_queue.txt").read_text().splitlines() if s.strip()]
    already = {e["slug"] for e in load_manifest(r2_client(), os.environ["R2_BUCKET"])}
    todo = [s for s in queue if s not in already][:count]
    print(f"Preparing {len(todo)} video(s): {', '.join(todo)}")

    done, failed = [], []
    # Archived newest-first on the page, so go through them last-to-first:
    # the next video to post ends up on top.
    for slug in reversed(todo):
        try:
            render(slug)
            archive(str(ROOT / "videos" / slug))
            done.append(slug)
        except (subprocess.CalledProcessError, SystemExit) as e:
            print(f"FAILED {slug}: {e}")
            failed.append(slug)

    print(f"\nPrepared {len(done)}, failed {len(failed)}: {', '.join(failed) or 'none'}")
    if not done:
        raise SystemExit("Nothing was prepared")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_COUNT)
