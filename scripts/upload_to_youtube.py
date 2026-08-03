"""
Uploads videos/<slug>/final.mp4 to YouTube using the metadata in
videos/<slug>/meta.json.

Auth comes from environment variables (set as GitHub Actions secrets):
    YOUTUBE_CLIENT_ID
    YOUTUBE_CLIENT_SECRET
    YOUTUBE_REFRESH_TOKEN

Usage:
    python scripts/upload_to_youtube.py videos/zoomies
"""
import json
import os
import sys
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def get_credentials():
    return Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )


def main(video_dir: str):
    video_dir = Path(video_dir)
    final = video_dir / "final.mp4"
    meta_path = video_dir / "meta.json"

    if not final.exists():
        raise SystemExit(f"Missing rendered video: {final}")
    meta = json.loads(meta_path.read_text())

    youtube = build("youtube", "v3", credentials=get_credentials())

    body = {
        "snippet": {
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta.get("tags", []),
            "categoryId": "15",  # Pets & Animals
        },
        "status": {
            "privacyStatus": meta.get("privacyStatus", "public"),
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(str(final), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress() * 100)}%")

    print(f"\nUpload complete: https://youtube.com/watch?v={response['id']}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/upload_to_youtube.py videos/<slug>")
    main(sys.argv[1])
