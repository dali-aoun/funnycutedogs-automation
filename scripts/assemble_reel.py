"""
Builds a vertical 9:16 Instagram Reel teaser from an already-rendered
videos/<slug>/final.mp4 (see assemble_video.py). Center-crops to 9:16,
trims to the first REEL_MAX_SECONDS seconds (a hook to drive traffic to
the full YouTube video), and scales to 1080x1920.

Usage:
    python scripts/assemble_reel.py videos/zoomies
"""
import subprocess
import sys
from pathlib import Path

REEL_MAX_SECONDS = 60


def run(cmd):
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main(video_dir: str):
    video_dir = Path(video_dir)
    final = video_dir / "final.mp4"
    reel = video_dir / "reel.mp4"

    if not final.exists():
        raise SystemExit(f"Missing rendered video: {final} (run assemble_video.py first)")

    crop_scale = "crop=ih*9/16:ih,scale=1080:1920"
    run([
        "ffmpeg", "-y", "-i", str(final),
        "-t", str(REEL_MAX_SECONDS),
        "-vf", crop_scale,
        "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-c:a", "aac",
        str(reel),
    ])
    print(f"\nDone: {reel}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/assemble_reel.py videos/<slug>")
    main(sys.argv[1])
