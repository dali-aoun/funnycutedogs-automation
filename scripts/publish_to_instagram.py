"""
Publishes videos/<slug>/reel.mp4 to Instagram as a Reel.

Instagram's Content Publishing API needs a public video URL (it fetches the
file itself), so this script:
  1. Uploads reel.mp4 to a Cloudflare R2 bucket (S3-compatible, free tier)
  2. Creates an IG media container pointing at the public R2 URL
  3. Polls the container until Instagram finishes downloading/processing it
  4. Publishes the container
  5. Deletes the temporary object from R2

Auth comes from environment variables (set as GitHub Actions secrets):
    IG_ACCESS_TOKEN         Meta system-user access token
    IG_BUSINESS_ACCOUNT_ID  Instagram Business Account ID
    R2_ACCESS_KEY_ID
    R2_SECRET_ACCESS_KEY
    R2_ENDPOINT             https://<account_id>.r2.cloudflarestorage.com
    R2_BUCKET
    R2_PUBLIC_URL           https://pub-xxxx.r2.dev (bucket's public dev URL)

Usage:
    python scripts/publish_to_instagram.py videos/zoomies
"""
import json
import os
import sys
import time
from pathlib import Path

import boto3
import requests

GRAPH_API = "https://graph.facebook.com/v19.0"
POLL_INTERVAL_SECONDS = 5
POLL_TIMEOUT_SECONDS = 300


def upload_to_r2(local_path: Path, object_key: str) -> str:
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    )
    bucket = os.environ["R2_BUCKET"]
    s3.upload_file(str(local_path), bucket, object_key, ExtraArgs={"ContentType": "video/mp4"})
    return s3, bucket


def delete_from_r2(s3, bucket: str, object_key: str):
    s3.delete_object(Bucket=bucket, Key=object_key)


def build_caption(meta: dict) -> str:
    # Raw URLs aren't clickable in an Instagram caption, so drive to the bio
    # link instead of reusing the YouTube description (which embeds one).
    hashtags = " ".join(f"#{tag.replace(' ', '')}" for tag in meta.get("tags", [])[:8])
    parts = [
        meta["title"],
        "",
        "🐾 Full video + more on the link in bio!",
        "",
        f"{hashtags} #shorts #short".strip(),
    ]
    return "\n".join(parts)


def create_container(video_url: str, caption: str) -> str:
    ig_user_id = os.environ["IG_BUSINESS_ACCOUNT_ID"]
    resp = requests.post(
        f"{GRAPH_API}/{ig_user_id}/media",
        data={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": os.environ["IG_ACCESS_TOKEN"],
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def wait_until_ready(container_id: str):
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        resp = requests.get(
            f"{GRAPH_API}/{container_id}",
            params={"fields": "status_code", "access_token": os.environ["IG_ACCESS_TOKEN"]},
            timeout=30,
        )
        resp.raise_for_status()
        status = resp.json()["status_code"]
        print(f"Container status: {status}")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise SystemExit("Instagram failed to process the video container")
        time.sleep(POLL_INTERVAL_SECONDS)
    raise SystemExit("Timed out waiting for Instagram to process the video")


def publish_container(container_id: str) -> str:
    ig_user_id = os.environ["IG_BUSINESS_ACCOUNT_ID"]
    resp = requests.post(
        f"{GRAPH_API}/{ig_user_id}/media_publish",
        data={"creation_id": container_id, "access_token": os.environ["IG_ACCESS_TOKEN"]},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def post_comment(media_id: str, text: str):
    """Best-effort: the Graph API has no pin-comment endpoint, so this just
    posts a top comment rather than a guaranteed-pinned one."""
    resp = requests.post(
        f"{GRAPH_API}/{media_id}/comments",
        data={"message": text, "access_token": os.environ["IG_ACCESS_TOKEN"]},
        timeout=30,
    )
    resp.raise_for_status()


def main(video_dir: str):
    video_dir = Path(video_dir)
    reel = video_dir / "reel.mp4"
    meta_path = video_dir / "meta.json"

    if not reel.exists():
        raise SystemExit(f"Missing rendered reel: {reel} (run assemble_reel.py first)")
    meta = json.loads(meta_path.read_text())

    object_key = f"{video_dir.name}-{int(time.time())}.mp4"
    s3, bucket = upload_to_r2(reel, object_key)
    video_url = f"{os.environ['R2_PUBLIC_URL']}/{object_key}"
    print(f"Uploaded to {video_url}")

    try:
        container_id = create_container(video_url, build_caption(meta))
        wait_until_ready(container_id)
        media_id = publish_container(container_id)
        print(f"\nPublished to Instagram: media id {media_id}")

        try:
            post_comment(media_id, "🔗 Full video + more tips: link in bio!")
            print("Posted link comment")
        except Exception as e:
            print(f"Could not post comment: {e}")
    finally:
        delete_from_r2(s3, bucket, object_key)
        print(f"Deleted temporary object {object_key} from R2")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/publish_to_instagram.py videos/<slug>")
    main(sys.argv[1])
