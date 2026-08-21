"""
Assembles a short-form (<=SHORT_MAX_SECONDS) vertical video directly from
clips + narration, for videos that are Shorts/Reels-only (no long-form
YouTube counterpart). Every clip is scaled and letterboxed onto a fixed
1080x1920 HD vertical canvas before concatenation, same robustness as
assemble_video.py's HD normalization.

Most Shorts-feed viewers scroll with sound off, so the first ~3 seconds
also get meta.json's "hookText" burned in as bold on-screen text (falls
back to the title if absent) — the hook has to land even when muted.

Expected folder layout, under videos/<slug>/:
    clips/01.mp4, 02.mp4, ...   (raw source clips, in play order)
    narration.mp3               (voice-over track)
    meta.json                   ({"title", "description", "tags", "privacyStatus"})

Usage:
    python scripts/assemble_short.py videos/short-why-dogs-howl
"""
import json
import subprocess
import sys
from pathlib import Path

TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
TARGET_FPS = 30
SHORT_MAX_SECONDS = 58
HOOK_DURATION_SECONDS = 3
HOOK_MAX_CHARS_PER_LINE = 22
HOOK_MAX_LINES = 3
HOOK_FONT_SIZE = 76
HOOK_LINE_HEIGHT = 96
HOOK_START_Y = 460

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def run(cmd):
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def find_font():
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return None


def wrap_hook(text):
    words = text.upper().split()
    lines = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if len(trial) <= HOOK_MAX_CHARS_PER_LINE:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:HOOK_MAX_LINES]


def escape_drawtext(text):
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\u2019")
        .replace("%", "\\%")
    )


def build_hook_filters(hook_text, font_path):
    lines = wrap_hook(hook_text)
    filters = []
    for i, line in enumerate(lines):
        y = HOOK_START_Y + i * HOOK_LINE_HEIGHT
        filters.append(
            f"drawtext=fontfile='{font_path}':text='{escape_drawtext(line)}':"
            f"fontsize={HOOK_FONT_SIZE}:fontcolor=white:borderw=6:bordercolor=black:"
            f"box=1:boxcolor=black@0.45:boxborderw=18:"
            f"x=(w-text_w)/2:y={y}:enable='between(t,0,{HOOK_DURATION_SECONDS})'"
        )
    return filters


def main(video_dir: str):
    video_dir = Path(video_dir)
    clips_dir = video_dir / "clips"
    narration = video_dir / "narration.mp3"
    reel = video_dir / "reel.mp4"
    meta = json.loads((video_dir / "meta.json").read_text())

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

    video_label = "vconcat"
    font_path = find_font()
    hook_text = meta.get("hookText")
    if hook_text and font_path:
        chain = []
        prev = "vconcat"
        for i, filt in enumerate(build_hook_filters(hook_text, font_path)):
            out = f"vhook{i}"
            chain.append(f"[{prev}]{filt}[{out}]")
            prev = out
        full_filter += ";" + ";".join(chain)
        video_label = prev

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", full_filter,
        "-map", f"[{video_label}]", "-map", "[a]",
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
