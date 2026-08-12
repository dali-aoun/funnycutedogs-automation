"""
Generates a custom YouTube thumbnail for videos/<slug>/final.mp4: grabs a
frame and overlays the video title on a dark gradient for readability.
Custom thumbnails meaningfully improve click-through rate over YouTube's
auto-picked frame.

Usage:
    python scripts/generate_thumbnail.py videos/zoomies
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

THUMB_WIDTH = 1280
THUMB_HEIGHT = 720
FRAME_TIME = "00:00:03"
ACCENT_COLOR = (240, 166, 60, 255)

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


def wrap_text(text, font, max_width, draw):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def main(video_dir: str):
    video_dir = Path(video_dir)
    final = video_dir / "final.mp4"
    thumbnail = video_dir / "thumbnail.jpg"
    frame = video_dir / "_thumb_frame.jpg"

    if not final.exists():
        raise SystemExit(f"Missing rendered video: {final}")
    meta = json.loads((video_dir / "meta.json").read_text())
    title = meta.get("thumbnailText", meta["title"]).upper()

    run(["ffmpeg", "-y", "-ss", FRAME_TIME, "-i", str(final), "-vframes", "1", "-q:v", "2", str(frame)])

    img = Image.open(frame).convert("RGB").resize((THUMB_WIDTH, THUMB_HEIGHT))
    img = ImageEnhance.Contrast(img).enhance(1.08)
    img = ImageEnhance.Color(img).enhance(1.15)
    img = img.convert("RGBA")

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    gradient_height = 360
    for y in range(gradient_height):
        alpha = int(210 * (y / gradient_height))
        y_pos = THUMB_HEIGHT - gradient_height + y
        draw.line([(0, y_pos), (THUMB_WIDTH, y_pos)], fill=(8, 8, 10, alpha))

    font_path = find_font()
    font_size = 84
    max_text_width = THUMB_WIDTH - 100

    def build_font(size):
        return ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default()

    font = build_font(font_size)
    lines = wrap_text(title, font, max_text_width, draw)
    while len(lines) > 3 and font_size > 46:
        font_size -= 6
        font = build_font(font_size)
        lines = wrap_text(title, font, max_text_width, draw)

    line_height = font_size + 16
    total_text_height = line_height * len(lines)
    y = THUMB_HEIGHT - 50 - total_text_height

    for line in lines:
        x = 50
        for dx, dy in [(-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, 2), (-2, 2), (2, -2)]:
            draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0, 255))
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_height

    draw.rectangle([(0, THUMB_HEIGHT - 10), (THUMB_WIDTH, THUMB_HEIGHT)], fill=ACCENT_COLOR)

    combined = Image.alpha_composite(img, overlay).convert("RGB")
    combined.save(thumbnail, quality=90)
    frame.unlink(missing_ok=True)
    print(f"\nDone: {thumbnail}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/generate_thumbnail.py videos/<slug>")
    main(sys.argv[1])
