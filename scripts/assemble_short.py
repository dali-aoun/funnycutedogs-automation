"""
Assembles a short-form (<=SHORT_MAX_SECONDS) vertical video directly from
clips + narration, for videos that are Shorts/Reels-only (no long-form
YouTube counterpart). Every clip is scaled and letterboxed onto a fixed
1080x1920 HD vertical canvas before concatenation, same robustness as
assemble_video.py's HD normalization.

Expected folder layout, under videos/<slug>/:
    clips/01.mp4, 02.mp4, ...   (raw source clips, in play order)
    narration.mp3               (voice-over track)
    meta.json                   ({"title", "description", "tags", "privacyStatus"})

Usage:
    python scripts/assemble_short.py videos/short-why-dogs-howl
"""
import subprocess
import sys
from pathlib import Path

TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
TARGET_FPS = 30
SHORT_MAX_SECONDS = 58


def run(cmd):
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main(video_dir: str):
    video_dir = Path(video_dir)
    clips_dir = video_dir / "clips"
    narration = video_dir / "narration.mp3"
    reel = video_dir / "reel.mp4"

    clips = sorted(clips_dir.glob("*.mp4"))
    if not clips:
        raise SystemExit(f"No clips found in {clips_dir}")
    if not narration.exists():
        raise SystemExit(f"Missing narration track: {narration}")

    clip_count = len(clips)
    inputs = []
    for clip in clips:
        inputs += ["-i", str(clip)]
    inputs += ["-i", str(narration)]
    narration_idx = clip_count

    scale_pad = (
        f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={TARGET_WIDTH}:{TARGET_HEIGHT}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={TARGET_FPS}"
    )
    per_clip_filters = ";".join(f"[{i}:v]{scale_pad}[v{i}]" for i in range(clip_count))
    concat_inputs = "".join(f"[v{i}]" for i in range(clip_count))
    concat_filter = f"{concat_inputs}concat=n={clip_count}:v=1:a=0[vconcat]"
    audio_filter = f"[{narration_idx}:a]volume=1.0[a]"
    full_filter = f"{per_clip_filters};{concat_filter};{audio_filter}"

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", full_filter,
        "-map", "[vconcat]", "-map", "[a]",
        "-t", str(SHORT_MAX_SECONDS),
        "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-c:a", "aac", "-shortest",
        str(reel),
    ]
    run(cmd)
    print(f"\nDone: {reel}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/assemble_short.py videos/<slug>")
    main(sys.argv[1])
