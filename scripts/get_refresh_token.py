"""
One-time local script to authorize this app against your YouTube channel
and obtain a refresh token for the GitHub Actions upload workflow.

Run this ONCE on your own machine:
    python scripts/get_refresh_token.py

It opens your browser, you approve access to your own YouTube channel,
and it prints the refresh token to store as the GitHub secret
YOUTUBE_REFRESH_TOKEN.
"""
import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

CLIENT_SECRET_FILE = Path(__file__).parent.parent / "secrets" / "client_secret.json"


def main():
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_FILE), SCOPES)
    credentials = flow.run_local_server(port=8080)

    print("\n=== Copy these values into GitHub repo secrets ===")
    print(f"YOUTUBE_CLIENT_ID={credentials.client_id}")
    print(f"YOUTUBE_CLIENT_SECRET={credentials.client_secret}")
    print(f"YOUTUBE_REFRESH_TOKEN={credentials.refresh_token}")

    out = Path(__file__).parent.parent / "secrets" / "token.json"
    out.write_text(
        json.dumps(
            {
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "refresh_token": credentials.refresh_token,
            },
            indent=2,
        )
    )
    print(f"\nAlso saved locally to {out} (not committed to git).")


if __name__ == "__main__":
    main()
