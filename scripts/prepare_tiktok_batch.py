"""
Prepares the next N Shorts for manual TikTok posting, ahead of time.

TikTok cannot be posted to unattended, so the creator uploads by hand. To let
a whole week be scheduled in one sitting, this renders the next N (default 21, a week at 3 a day) queued
Shorts (the same videos YouTube and Instagram will publish) and archives each
one with its caption, so funnycutedogs.com/tiktok/ lists them in posting
order. It does NOT upload to YouTube or Instagram and does NOT touch the
queue; the daily workflow keeps publishing there on its own.

Videos already in the manifest are skipped, so running it twice never
duplicates work. Pass "refresh" to re-render them anyway (they keep their
place in the list).

Env: PEXELS_API_KEY plus the R2_* variables used by archive_for_tiktok.py.

Usage:
    python scripts/prepare_tiktok_batch.py 21 [refresh]
"""
import os
import subprocess
import sys
from pathlib import Path

from archive_for_tiktok import REQUIRED_ENV, load_manifest, main as archive, next_seq, r2_client, with_seq

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
DEFAULT_COUNT = 21  # 3 TikTok posts a day (12:00, 19:55, 23:55) for a week
RENDER_STEPS = ("fetch_clips.py", "generate_narration.py", "assemble_short.py")


def render(slug: str):
    video_dir = ROOT / "videos" / slug
    for step in RENDER_STEPS:
        subprocess.run([sys.executable, str(SCRIPTS / step), str(video_dir)], check=True)


def main(count: int, refresh: bool = False):
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing or not os.environ.get("PEXELS_API_KEY"):
        raise SystemExit(f"Missing environment: {', '.join(missing) or 'PEXELS_API_KEY'}")

    queue = [s.strip() for s in (ROOT / "videos" / "shorts_queue.txt").read_text().splitlines() if s.strip()]
    manifest = with_seq(load_manifest(r2_client(), os.environ["R2_BUCKET"]))
    already = {e["slug"] for e in manifest}
    first_seq = next_seq(manifest)
    todo = [s for s in queue if refresh or s not in already][:count]
    print(f"Preparing {len(todo)} video(s): {', '.join(todo)}")

    done, failed = [], []
    # Each video gets its posting order from its place in the queue; the page
    # shows lowest `seq` first, so a new batch never jumps ahead of videos not
    # posted yet. Archived last-to-first so the list itself also reads top-down.
    for seq, slug in reversed(list(enumerate(todo, start=first_seq))):
        try:
            render(slug)
            archive(str(ROOT / "videos" / slug), seq)
            done.append(slug)
        except (subprocess.CalledProcessError, SystemExit) as e:
            print(f"FAILED {slug}: {e}")
            failed.append(slug)

    print(f"\nPrepared {len(done)}, failed {len(failed)}: {', '.join(failed) or 'none'}")
    if not done:
        raise SystemExit("Nothing was prepared")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_COUNT, "refresh" in sys.argv[2:])
