"""
Keeps a downloadable copy of each published Short for manual TikTok upload
from a computer, and maintains the list the website page reads.

TikTok does not allow unattended public posting for a private tool, so the
creator uploads the videos by hand (TikTok Studio on desktop). This script:
  1. Uploads videos/<slug>/reel.mp4 to the R2 bucket as tiktok/<slug>.mp4
     (served as a download)
  2. Adds an entry (title, description, hashtags, caption, video URL) to
     tiktok/manifest.json, which funnycutedogs.com/tiktok/ renders
  3. Keeps only the newest MAX_ENTRIES videos and deletes the older files

Auth comes from the same environment variables as publish_to_instagram.py:
    R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT, R2_BUCKET, R2_PUBLIC_URL

If they are missing the script exits 0 without doing anything.

Usage:
    python scripts/archive_for_tiktok.py videos/zoomies
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from tiktok_captions import build_caption

MANIFEST_KEY = "tiktok/manifest.json"
MAX_ENTRIES = 45
REQUIRED_ENV = ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT", "R2_BUCKET", "R2_PUBLIC_URL")


def r2_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    )


def load_manifest(s3, bucket: str) -> list:
    try:
        body = s3.get_object(Bucket=bucket, Key=MANIFEST_KEY)["Body"].read()
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return []
        raise
    return json.loads(body)


def save_manifest(s3, bucket: str, entries: list):
    s3.put_object(
        Bucket=bucket,
        Key=MANIFEST_KEY,
        Body=json.dumps(entries, ensure_ascii=False, indent=1).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
        CacheControl="no-cache, max-age=0",
    )


def main(video_dir: str):
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        print(f"R2 not configured (missing {', '.join(missing)}), skipping TikTok archive.")
        return

    video_dir = Path(video_dir)
    slug = video_dir.name
    reel = video_dir / "reel.mp4"
    if not reel.exists():
        raise SystemExit(f"Missing rendered reel: {reel}")
    meta = json.loads((video_dir / "meta.json").read_text(encoding="utf-8"))

    s3 = r2_client()
    bucket = os.environ["R2_BUCKET"]
    key = f"tiktok/{slug}.mp4"
    s3.upload_file(
        str(reel), bucket, key,
        ExtraArgs={
            "ContentType": "video/mp4",
            "ContentDisposition": f'attachment; filename="{slug}.mp4"',
        },
    )
    video_url = f"{os.environ['R2_PUBLIC_URL'].rstrip('/')}/{key}"
    print(f"Archived {reel.name} at {video_url}")

    entry = build_caption(meta)
    entry.update(
        slug=slug,
        video_url=video_url,
        added_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )

    # A video prepared ahead of time by prepare_tiktok_batch.py keeps its place
    # in the posting order when the daily workflow archives it again.
    existing = load_manifest(s3, bucket)
    if any(e.get("slug") == slug for e in existing):
        entries = [entry if e.get("slug") == slug else e for e in existing]
    else:
        entries = [entry] + existing
    for old in entries[MAX_ENTRIES:]:
        s3.delete_object(Bucket=bucket, Key=f"tiktok/{old['slug']}.mp4")
        print(f"Removed old archive {old['slug']}")
    save_manifest(s3, bucket, entries[:MAX_ENTRIES])
    print(f"Manifest updated ({min(len(entries), MAX_ENTRIES)} videos)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/archive_for_tiktok.py videos/<slug>")
    main(sys.argv[1])
