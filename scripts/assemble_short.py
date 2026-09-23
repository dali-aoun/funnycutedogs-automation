"""
Assembles a short-form (<=SHORT_MAX_SECONDS) vertical video directly from
clips + narration, for videos that are Shorts/Reels-only (no long-form
YouTube counterpart). Every clip is scaled and letterboxed onto a fixed
1080x1920 HD vertical canvas before concatenation, same robustness as
assemble_video.py's HD normalization.

Most Shorts-feed viewers scroll with sound off, so the first ~3 seconds
also get meta.json's "hookText" burned in as bold on-screen text (falls
back to the title if absent) — the hook has to land even when muted.

The last ~3 seconds burn in a "FOLLOW FOR MORE" CTA. YouTube's pinned-
comment CTA isn't actually pinnable via the Data API (see youtube_lib.py),
and Shorts viewers rarely open the comment tray anyway, so an on-screen
CTA is the only reliable way to ask viewers to subscribe.

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

CTA_TEXT = "FOLLOW FOR MORE"
CTA_DURATION_SECONDS = 3
CTA_MIN_DURATION_SECONDS = 1.5
CTA_FONT_SIZE = 64
CTA_START_Y = 1650

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


def wrap_text(text, max_chars_per_line, max_lines):
    words = text.upper().split()
    lines = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if len(trial) <= max_chars_per_line:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:max_lines]


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def escape_drawtext(text):
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\u2019")
        .replace("%", "\\%")
    )


def escape_fontfile(font_path):
    # ffmpeg's filtergraph parser splits on ":" even inside quotes, which
    # breaks Windows paths like "C:/Windows/Fonts/...". Doesn't affect the
    # Linux font paths used in CI, but needed for local Windows testing.
    return font_path.replace(":", "\\:")


def build_hook_filters(hook_text, font_path):
    font_path = escape_fontfile(font_path)
    lines = wrap_text(hook_text, HOOK_MAX_CHARS_PER_LINE, HOOK_MAX_LINES)
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


def build_cta_filter(font_path, start, end):
    font_path = escape_fontfile(font_path)
    line = wrap_text(CTA_TEXT, HOOK_MAX_CHARS_PER_LINE, 1)[0]
    return (
        f"drawtext=fontfile='{font_path}':text='{escape_drawtext(line)}':"
        f"fontsize={CTA_FONT_SIZE}:fontcolor=white:borderw=6:bordercolor=black:"
        f"box=1:boxcolor=black@0.45:boxborderw=18:"
        f"x=(w-text_w)/2:y={CTA_START_Y}:enable='between(t,{start},{end})'"
    )


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
    chain = []
    prev = "vconcat"

    hook_text = meta.get("hookText")
    if hook_text and font_path:
        for filt in build_hook_filters(hook_text, font_path):
            out = f"vhook{len(chain)}"
            chain.append(f"[{prev}]{filt}[{out}]")
            prev = out

    if font_path:
        clip_durations = [probe_duration(c) for c in clips]
        narration_duration = probe_duration(narration)
        final_duration = min(sum(clip_durations), narration_duration, SHORT_MAX_SECONDS)

        # Prefer the CTA fully after the hook window. Short narration (a
        # handful of words) can make the whole video only a few seconds
        # long though, leaving too little room after the hook — in that
        # case let the CTA overlap the hook's tail rather than flash by
        # too briefly to read.
        room_after_hook = final_duration - HOOK_DURATION_SECONDS
        if room_after_hook >= CTA_MIN_DURATION_SECONDS:
            cta_start = max(final_duration - CTA_DURATION_SECONDS, HOOK_DURATION_SECONDS)
        elif final_duration >= CTA_MIN_DURATION_SECONDS:
            cta_start = final_duration - CTA_MIN_DURATION_SECONDS
        else:
            cta_start = None

        if cta_start is not None:
            filt = build_cta_filter(font_path, round(cta_start, 2), round(final_duration, 2))
            out = f"vcta{len(chain)}"
            chain.append(f"[{prev}]{filt}[{out}]")
            prev = out

    if chain:
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
