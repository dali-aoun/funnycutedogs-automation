"""
Shared YouTube Data API v3 upload helper, used by upload_to_youtube.py
(long-form) and upload_short_to_youtube.py (Shorts).

Auth comes from environment variables (set as GitHub Actions secrets):
    YOUTUBE_CLIENT_ID
    YOUTUBE_CLIENT_SECRET
    YOUTUBE_REFRESH_TOKEN
"""
import os
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
PETS_AND_ANIMALS_CATEGORY_ID = "15"


def get_credentials() -> Credentials:
    return Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )


def upload_video(video_path: Path, title: str, description: str, tags: list, privacy_status: str) -> str:
    youtube = build("youtube", "v3", credentials=get_credentials())

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": PETS_AND_ANIMALS_CATEGORY_ID,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress() * 100)}%")

    return response["id"]
