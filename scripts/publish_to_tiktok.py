"""
Sends videos/<slug>/reel.mp4 to the TikTok account's inbox as a draft.

TikTok does not allow fully automatic public posting for a private tool
(Direct Post requires a user-facing form and an audit), so this uses the
"Upload to inbox" flow: the video lands in the creator's TikTok app as a
draft notification and is published there with one tap.

Auth comes from environment variables (GitHub Actions secrets):
    TIKTOK_CLIENT_KEY
    TIKTOK_CLIENT_SECRET
    TIKTOK_REFRESH_TOKEN

If any of them is missing the script exits 0 without doing anything, and the
caller step is also continue-on-error, so a TikTok problem can never block
the YouTube / Instagram publish or the queue dequeue.

Usage:
    python scripts/publish_to_tiktok.py videos/zoomies
"""
import os
import sys
import time
from pathlib import Path

import requests

API = "https://open.tiktokapis.com/v2"
SINGLE_CHUNK_MAX_BYTES = 64 * 1024 * 1024
STATUS_TIMEOUT_SECONDS = 90
STATUS_INTERVAL_SECONDS = 5
REQUIRED_ENV = ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REFRESH_TOKEN")


def refresh_access_token() -> str:
    resp = requests.post(
        f"{API}/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": os.environ["TIKTOK_CLIENT_KEY"],
            "client_secret": os.environ["TIKTOK_CLIENT_SECRET"],
            "grant_type": "refresh_token",
            "refresh_token": os.environ["TIKTOK_REFRESH_TOKEN"],
        },
        timeout=30,
    )
    body = resp.json()
    if resp.status_code != 200 or "access_token" not in body:
        raise SystemExit(f"TikTok token refresh failed: {resp.status_code} {body}")
    new_refresh = body.get("refresh_token")
    if new_refresh and new_refresh != os.environ["TIKTOK_REFRESH_TOKEN"]:
        print(
            "NOTICE: TikTok returned a different refresh token. The stored one "
            "keeps working until it expires (365 days after issue); re-run the "
            "authorization before then."
        )
    return body["access_token"]


def init_inbox_upload(access_token: str, video_size: int) -> dict:
    resp = requests.post(
        f"{API}/post/publish/inbox/video/init/",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        json={
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": video_size,
                "total_chunk_count": 1,
            }
        },
        timeout=30,
    )
    body = resp.json()
    if resp.status_code != 200 or body.get("error", {}).get("code") != "ok":
        raise SystemExit(f"TikTok upload init failed: {resp.status_code} {body}")
    return body["data"]


def put_video(upload_url: str, video_path: Path, video_size: int):
    with video_path.open("rb") as f:
        resp = requests.put(
            upload_url,
            headers={
                "Content-Type": "video/mp4",
                "Content-Length": str(video_size),
                "Content-Range": f"bytes 0-{video_size - 1}/{video_size}",
            },
            data=f,
            timeout=300,
        )
    if resp.status_code not in (200, 201, 206):
        raise SystemExit(f"TikTok video upload failed: {resp.status_code} {resp.text[:300]}")


def wait_for_inbox(access_token: str, publish_id: str):
    deadline = time.monotonic() + STATUS_TIMEOUT_SECONDS
    status = "UNKNOWN"
    while time.monotonic() < deadline:
        resp = requests.post(
            f"{API}/post/publish/status/fetch/",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
            json={"publish_id": publish_id},
            timeout=30,
        )
        body = resp.json()
        status = body.get("data", {}).get("status", "UNKNOWN")
        print(f"TikTok status: {status}")
        if status in ("SEND_TO_USER_INBOX", "PUBLISH_COMPLETE"):
            return
        if status == "FAILED":
            raise SystemExit(f"TikTok reported failure: {body}")
        time.sleep(STATUS_INTERVAL_SECONDS)
    print(f"TikTok status still {status} after {STATUS_TIMEOUT_SECONDS}s; the draft may arrive shortly.")


def main(video_dir: str):
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        print(f"TikTok not configured (missing {', '.join(missing)}), skipping.")
        return

    reel = Path(video_dir) / "reel.mp4"
    if not reel.exists():
        raise SystemExit(f"Missing rendered reel: {reel}")
    video_size = reel.stat().st_size
    if video_size > SINGLE_CHUNK_MAX_BYTES:
        raise SystemExit(f"{reel} is {video_size} bytes, over the single-chunk limit")

    access_token = refresh_access_token()
    data = init_inbox_upload(access_token, video_size)
    put_video(data["upload_url"], reel, video_size)
    print(f"Uploaded {reel.name} to TikTok (publish_id {data['publish_id']})")
    wait_for_inbox(access_token, data["publish_id"])
    print("\nDraft sent to the TikTok inbox: open the TikTok app and tap Publish.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/publish_to_tiktok.py videos/<slug>")
    main(sys.argv[1])
