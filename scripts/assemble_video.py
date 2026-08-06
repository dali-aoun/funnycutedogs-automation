"""
Assembles the long-form video from raw clips + narration (+ optional
background music and watermark) using ffmpeg. Every clip is scaled and
letterboxed onto a fixed 1920x1080 HD canvas before concatenation, so
mismatched source resolutions/aspect ratios/framerates never break (or
silently degrade) the output. Fails if the result is under 60 seconds,
since this is meant to be the long-form counterpart to the <60s Short/Reel.

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
TARGET_WIDTH = 1920
TARGET_HEIGHT = 1080
TARGET_FPS = 30
MIN_DURATION_SECONDS = 60


def run(cmd):
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def ffprobe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def main(video_dir: str):
    video_dir = Path(video_dir)
    clips_dir = video_dir / "clips"
    narration = video_dir / "narration.mp3"
    music = video_dir / "music.mp3"
    final = video_dir / "final.mp4"

    clips = sorted(clips_dir.glob("*.mp4"))
    if not clips:
        raise SystemExit(f"No clips found in {clips_dir}")
    if not narration.exists():
        raise SystemExit(f"Missing narration track: {narration}")

    has_watermark = WATERMARK.exists()
    has_music = music.exists()
    clip_count = len(clips)

    inputs = []
    for clip in clips:
        inputs += ["-i", str(clip)]

    watermark_idx = clip_count
    if has_watermark:
        inputs += ["-i", str(WATERMARK)]

    narration_idx = clip_count + (1 if has_watermark else 0)
    inputs += ["-i", str(narration)]

    music_idx = narration_idx + 1
    if has_music:
        inputs += ["-i", str(music)]

    # Normalize every clip onto the same HD canvas so the concat filter
    # never chokes on mismatched resolutions/aspect ratios/framerates.
    scale_pad = (
        f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={TARGET_WIDTH}:{TARGET_HEIGHT}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={TARGET_FPS}"
    )
    per_clip_filters = ";".join(f"[{i}:v]{scale_pad}[v{i}]" for i in range(clip_count))
    concat_inputs = "".join(f"[v{i}]" for i in range(clip_count))
    concat_filter = f"{concat_inputs}concat=n={clip_count}:v=1:a=0[vconcat]"

    if has_watermark:
        video_filter = (
            f"{per_clip_filters};{concat_filter};"
            f"[{watermark_idx}:v]scale=150:-1[wm];"
            f"[vconcat][wm]overlay=W-w-24:H-h-24[v]"
        )
        video_map = "[v]"
    else:
        video_filter = f"{per_clip_filters};{concat_filter}"
        video_map = "[vconcat]"

    if has_music:
        audio_filter = (
            f"[{narration_idx}:a]volume=1.0[narr];"
            f"[{music_idx}:a]volume=0.15[bg];"
            f"[narr][bg]amix=inputs=2:duration=first[a]"
        )
    else:
        audio_filter = f"[{narration_idx}:a]volume=1.0[a]"

    full_filter = f"{video_filter};{audio_filter}"

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", full_filter,
        "-map", video_map, "-map", "[a]",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-c:a", "aac", "-shortest",
        str(final),
    ]
    run(cmd)

    duration = ffprobe_duration(final)
    print(f"Final duration: {duration:.1f}s")
    if duration < MIN_DURATION_SECONDS:
        raise SystemExit(
            f"final.mp4 is only {duration:.1f}s (< {MIN_DURATION_SECONDS}s required for the "
            f"long-form video) — lengthen the narration script or add more/longer clips"
        )

    print(f"\nDone: {final}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/assemble_video.py videos/<slug>")
    main(sys.argv[1])
