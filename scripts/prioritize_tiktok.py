"""
Moves the given videos to the top of the "À faire" list on funnycutedogs.com/tiktok/
(the page sorts on `seq`, lowest first) without re-rendering anything.

Env: the R2_* variables used by archive_for_tiktok.py.

Usage:
    python scripts/prioritize_tiktok.py short-a,short-b,short-c
"""
import os
import sys

from archive_for_tiktok import REQUIRED_ENV, load_manifest, r2_client, save_manifest, with_seq


def main(slugs: list):
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        raise SystemExit(f"Missing environment: {', '.join(missing)}")

    s3, bucket = r2_client(), os.environ["R2_BUCKET"]
    entries = with_seq(load_manifest(s3, bucket))
    known = {e["slug"] for e in entries}
    wanted = [s for s in slugs if s in known]
    for s in slugs:
        if s not in known:
            print(f"Not on the page, skipped: {s}")

    first = min(e["seq"] for e in entries) - len(wanted)
    new_seq = {slug: first + i for i, slug in enumerate(wanted)}  # keeps the order given
    updated = [{**e, "seq": new_seq[e["slug"]]} if e["slug"] in new_seq else e for e in entries]
    save_manifest(s3, bucket, updated)
    print(f"{len(wanted)} video(s) moved to the top: {', '.join(wanted)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/prioritize_tiktok.py slug1,slug2,...")
    main([s for s in sys.argv[1].split(",") if s])
