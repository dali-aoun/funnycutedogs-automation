"""
Assembles a short-form vertical video (6-10s, see TARGET_* constants)
directly from clips + narration, for videos that are Shorts/Reels-only (no long-form
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

from clip_motion import best_start, motion_profile, plan_segments

TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
TARGET_FPS = 30
SHORT_MAX_SECONDS = 58
# Final length is set explicitly. The old "-shortest" gave 6-25s at random
# (it followed neither the narration nor the clips), and the data says the
# shortest Shorts win: 6s -> 91% watched, <15s -> ~3x the retention of 25s+.
TARGET_MIN_SECONDS = 6
TARGET_MAX_SECONDS = 10
TARGET_TAIL_SECONDS = 2.5
NARRATION_END_PADDING_SECONDS = 0.5
HOOK_DURATION_SECONDS = 3
HOOK_MAX_CHARS_PER_LINE = 22
HOOK_MAX_LINES = 3
HOOK_FONT_SIZE = 76
HOOK_LINE_HEIGHT = 96
HOOK_START_Y = 460

CTA_TEXT = "FOLLOW FOR MORE"
CTA_DURATION_SECONDS = 2.5
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


def choose_duration(narration_seconds: float, clips_seconds: float) -> float:
    """Narration plus a short tail, kept inside the 6-10s band, but never so
    short that the narration is cut off, and never longer than the footage."""
    target = min(max(narration_seconds + TARGET_TAIL_SECONDS, TARGET_MIN_SECONDS), TARGET_MAX_SECONDS)
    target = max(target, narration_seconds + NARRATION_END_PADDING_SECONDS)
    return round(min(target, clips_seconds, SHORT_MAX_SECONDS), 2)


def pick_start(clip: Path, length: float, duration: float) -> float:
    """Most animated start for a `length`-second cut; 0 if motion can't be read."""
    try:
        return best_start(motion_profile(clip), length, duration)
    except (subprocess.CalledProcessError, OSError) as e:
        print(f"Motion analysis failed for {clip.name} ({e}); starting at 0s")
        return 0.0


def clip_filter(i: int) -> str:
    """Fit input i on the 9:16 canvas without black bars: the whole clip stays
    visible in the middle, over a blurred, darkened, enlarged copy of itself.
    (A plain center-crop would drop one of the dogs in side-by-side scenes.)
    The background is blurred at a quarter of the resolution, which is much
    cheaper and just as smooth."""
    bg_w, bg_h = TARGET_WIDTH // 4, TARGET_HEIGHT // 4
    return (
        f"[{i}:v]fps={TARGET_FPS},split=2[s{i}a][s{i}b];"
        f"[s{i}a]scale={bg_w}:{bg_h}:force_original_aspect_ratio=increase,crop={bg_w}:{bg_h},"
        f"boxblur=6:2,scale={TARGET_WIDTH}:{TARGET_HEIGHT},eq=brightness=-0.12[bg{i}];"
        f"[s{i}b]scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=decrease[fg{i}];"
        f"[bg{i}][fg{i}]overlay=(W-w)/2:(H-h)/2,setsar=1[v{i}]"
    )


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
    clip_durations = [probe_duration(c) for c in clips]
    clip_total = sum(clip_durations)
    final_duration = choose_duration(probe_duration(narration), clip_total)
    print(f"Final duration: {final_duration}s (clips total {clip_total:.1f}s)")

    # Each clip contributes an equal share of the final length, taken from its
    # most animated stretch rather than from second 0.
    segments = plan_segments(clip_durations, final_duration)
    inputs = []
    for clip, duration, length in zip(clips, clip_durations, segments):
        start = pick_start(clip, length, duration)
        print(f"{clip.name}: using {length}s from {start}s")
        inputs += ["-ss", str(start), "-t", str(length), "-i", str(clip)]
    inputs += ["-i", str(narration)]
    narration_idx = clip_count

    per_clip_filters = ";".join(clip_filter(i) for i in range(clip_count))
    concat_inputs = "".join(f"[v{i}]" for i in range(clip_count))
    concat_filter = f"{concat_inputs}concat=n={clip_count}:v=1:a=0[vconcat]"
    # apad keeps the audio track running to the end so the explicit -t below
    # (not stream lengths) decides where the video stops.
    audio_filter = f"[{narration_idx}:a]volume=1.0,apad[a]"
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
        # Prefer the CTA fully after the hook window; if the video is too
        # short for both, let it overlap the hook's tail rather than flash
        # by too briefly to read.
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
        "-t", str(final_duration),
        "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-c:a", "aac",
        str(reel),
    ]
    run(cmd)
    print(f"\nDone: {reel}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/assemble_short.py videos/<slug>")
    main(sys.argv[1])
