"""
Assembles a video from raw clips + narration (+ optional background music
and watermark) using ffmpeg.

Expected folder layout for each video, under videos/<slug>/:
    clips/01.mp4, 02.mp4, ...   (raw source clips, in play order)
    narration.mp3               (voice-over track)
    music.mp3                   (optional background music, mixed low)
    meta.json                   ({"title", "description", "tags", "privacyStatus"})

Usage:
    python scripts/assemble_video.py videos/zoomies
"""
import subprocess
import sys
from pathlib import Path

WATERMARK = Path(__file__).parent.parent / "assets" / "logo_watermark.png"


def run(cmd):
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main(video_dir: str):
    video_dir = Path(video_dir)
    clips_dir = video_dir / "clips"
    narration = video_dir / "narration.mp3"
    music = video_dir / "music.mp3"
    concat_list = video_dir / "_concat.txt"
    raw_concat = video_dir / "_raw_concat.mp4"
    final = video_dir / "final.mp4"

    clips = sorted(clips_dir.glob("*.mp4"))
    if not clips:
        raise SystemExit(f"No clips found in {clips_dir}")
    if not narration.exists():
        raise SystemExit(f"Missing narration track: {narration}")

    # 1. Concatenate raw clips (video + their own audio)
    concat_list.write_text("".join(f"file '{c.resolve()}'\n" for c in clips))
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c", "copy", str(raw_concat),
    ])

    # 2. Mix narration (and optional music) over the concatenated clips,
    #    overlay the channel watermark bottom-right.
    filter_complex = "[0:v]"
    if WATERMARK.exists():
        filter_complex = (
            "[1:v]scale=120:-1[wm];"
            "[0:v][wm]overlay=W-w-24:H-h-24[v]"
        )
        video_map = "[v]"
    else:
        video_map = "0:v"

    inputs = ["-i", str(raw_concat)]
    if WATERMARK.exists():
        inputs += ["-i", str(WATERMARK)]
    inputs += ["-i", str(narration)]
    narration_idx = 2 if WATERMARK.exists() else 1

    if music.exists():
        inputs += ["-i", str(music)]
        music_idx = narration_idx + 1
        audio_filter = (
            f"[{narration_idx}:a]volume=1.0[narr];"
            f"[{music_idx}:a]volume=0.15[bg];"
            f"[narr][bg]amix=inputs=2:duration=first[a]"
        )
    else:
        audio_filter = f"[{narration_idx}:a]volume=1.0[a]"

    if WATERMARK.exists():
        full_filter = f"{filter_complex};{audio_filter}"
    else:
        full_filter = audio_filter

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", full_filter,
        "-map", video_map, "-map", "[a]",
        "-c:v", "libx264", "-c:a", "aac", "-shortest",
        str(final),
    ]
    run(cmd)

    concat_list.unlink(missing_ok=True)
    raw_concat.unlink(missing_ok=True)
    print(f"\nDone: {final}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/assemble_video.py videos/<slug>")
    main(sys.argv[1])
