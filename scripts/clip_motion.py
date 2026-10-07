"""
Finds the most animated stretch of a stock clip, so a Short starts on action
instead of on the (often empty) first second of the footage.

Motion is measured as the mean absolute difference between consecutive
low-resolution grayscale frames, decoded by ffmpeg. Pure Python on purpose:
the CI image has no numpy and the frames are tiny.
"""
import subprocess

SAMPLE_FPS = 4
FRAME_WIDTH = 48
FRAME_HEIGHT = 27
FRAME_BYTES = FRAME_WIDTH * FRAME_HEIGHT
SEARCH_STEP_SECONDS = 0.25


def motion_profile(path) -> list:
    """Motion score between each pair of consecutive sampled frames."""
    out = subprocess.run(
        [
            "ffmpeg", "-v", "error", "-i", str(path),
            "-vf", f"fps={SAMPLE_FPS},scale={FRAME_WIDTH}:{FRAME_HEIGHT},format=gray",
            "-f", "rawvideo", "-",
        ],
        capture_output=True, check=True,
    ).stdout
    frames = [out[i:i + FRAME_BYTES] for i in range(0, len(out) - FRAME_BYTES + 1, FRAME_BYTES)]
    return [
        sum(abs(a - b) for a, b in zip(prev, cur)) / FRAME_BYTES
        for prev, cur in zip(frames, frames[1:])
    ]


def best_start(profile: list, window_seconds: float, clip_seconds: float) -> float:
    """Start time (seconds) of the window with the most motion; 0 if unknown."""
    latest = clip_seconds - window_seconds
    window_steps = max(1, round(window_seconds * SAMPLE_FPS))
    if latest <= 0 or len(profile) < window_steps:
        return 0.0

    best, best_score = 0.0, -1.0
    start = 0.0
    while start <= latest + 1e-9:
        first = int(start * SAMPLE_FPS)
        score = sum(profile[first:first + window_steps])
        if score > best_score:
            best, best_score = start, score
        start += SEARCH_STEP_SECONDS
    return round(best, 2)


def plan_segments(durations: list, total: float) -> list:
    """Split `total` seconds across clips as evenly as their lengths allow:
    a clip shorter than its share gives its leftover to the others."""
    lengths = [0.0] * len(durations)
    open_idx = list(range(len(durations)))
    remaining = total
    while open_idx and remaining > 1e-6:
        share = remaining / len(open_idx)
        capped = [i for i in open_idx if durations[i] - lengths[i] <= share + 1e-9]
        if not capped:
            for i in open_idx:
                lengths[i] += share
            break
        for i in capped:
            remaining -= durations[i] - lengths[i]
            lengths[i] = durations[i]
            open_idx.remove(i)
    return [round(length, 2) for length in lengths]
