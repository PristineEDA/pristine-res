#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


DEFAULT_SRC = Path("images/logo/logo-letter-v3/logo.png")
DEFAULT_OUT_DIR = Path("images/logo/logo-official")
DEFAULT_SIZES = (16, 32, 64, 128, 256, 512)
DEFAULT_ICO_SIZES = (16, 32, 48, 64, 128, 256)


def parse_sizes(value: str) -> tuple[int, ...]:
    try:
        sizes = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("sizes must be comma-separated integers") from exc

    if not sizes:
        raise argparse.ArgumentTypeError("at least one size is required")
    if any(size <= 0 for size in sizes):
        raise argparse.ArgumentTypeError("sizes must be positive")
    return sizes


def make_round_mask(size: int, radius: int, supersample: int) -> Image.Image:
    large_size = size * supersample
    large_radius = radius * supersample
    mask = Image.new("L", (large_size, large_size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle(
        (0, 0, large_size - 1, large_size - 1),
        radius=large_radius,
        fill=255,
    )
    return mask.resize((size, size), Image.Resampling.LANCZOS)


def apply_rounded_alpha(img: Image.Image, radius_ratio: float, supersample: int) -> Image.Image:
    rgba = img.convert("RGBA")
    width, height = rgba.size
    if width != height:
        raise ValueError(f"source image must be square, got {width}x{height}")

    radius = round(width * radius_ratio)
    if radius <= 0:
        raise ValueError("radius ratio is too small; computed radius must be positive")
    if radius > width // 2:
        raise ValueError("radius ratio is too large; computed radius exceeds half the image size")

    mask = make_round_mask(width, radius, supersample)
    alpha = ImageChops.multiply(rgba.getchannel("A"), mask)
    rounded = rgba.copy()
    rounded.putalpha(alpha)
    return rounded


def save_png_sizes(master: Image.Image, out_dir: Path, sizes: tuple[int, ...]) -> None:
    for size in sizes:
        resized = master.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(out_dir / f"logo-{size}.png", format="PNG", optimize=True)


def save_ico(master: Image.Image, out_dir: Path, sizes: tuple[int, ...]) -> None:
    ico_sizes = [(size, size) for size in sizes]
    master.save(out_dir / "logo.ico", format="ICO", sizes=ico_sizes)


def save_icns(master: Image.Image, out_dir: Path) -> None:
    try:
        master.save(out_dir / "logo.icns", format="ICNS")
    except Exception as exc:
        raise RuntimeError(
            "Pillow in this environment could not write logo.icns. "
            "The PNG and ICO outputs were generated, but ICNS needs a Pillow build "
            "with ICNS write support or a platform icon tool."
        ) from exc


def make_preview(out_dir: Path) -> None:
    sizes = (128, 64, 32, 16)
    source = Image.open(out_dir / "logo.png").convert("RGBA")
    width = 860
    height = 250
    preview = Image.new("RGB", (width, height), (240, 247, 252))
    draw = ImageDraw.Draw(preview)
    draw.text((16, 14), "logo-official preview: light/dark + 128/64/32/16 checks", fill=(35, 55, 70))

    x = 22
    for bg in ((255, 255, 255), (16, 18, 22)):
        draw.rounded_rectangle((x, 48, x + 360, 222), radius=10, fill=bg, outline=(196, 214, 226))
        cx = x + 22
        for size in sizes:
            icon = source.resize((size, size), Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            canvas.alpha_composite(icon)
            preview.paste(canvas.convert("RGB"), (cx, 76 + (128 - size) // 2), canvas)
            cx += size + 24
        x += 402

    preview.save(out_dir / "logo-preview-light-dark-small.png", format="PNG", optimize=True)


def build(args: argparse.Namespace) -> None:
    src = args.src
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if not src.exists():
        raise FileNotFoundError(f"source logo not found: {src}")

    with Image.open(src) as loaded:
        source = loaded.convert("RGBA")

    width, height = source.size
    if width != height:
        raise ValueError(f"source image must be square, got {width}x{height}")
    if (width, height) != (1024, 1024):
        print(f"Warning: expected 1024x1024 source, got {width}x{height}.", file=sys.stderr)

    shutil.copy2(src, out_dir / "logo-square-source.png")

    rounded = apply_rounded_alpha(source, args.radius_ratio, args.supersample)
    rounded.save(out_dir / "logo.png", format="PNG", optimize=True)

    save_png_sizes(rounded, out_dir, args.sizes)
    save_ico(rounded, out_dir, args.ico_sizes)
    save_icns(rounded, out_dir)

    if args.preview:
        make_preview(out_dir)

    generated = [
        "logo-square-source.png",
        "logo.png",
        *(f"logo-{size}.png" for size in args.sizes),
        "logo.ico",
        "logo.icns",
    ]
    if args.preview:
        generated.append("logo-preview-light-dark-small.png")

    print(f"Generated official logo assets in {out_dir}:")
    for name in generated:
        print(f"  {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build rounded official logo assets.")
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--radius-ratio", type=float, default=0.20)
    parser.add_argument("--sizes", type=parse_sizes, default=DEFAULT_SIZES)
    parser.add_argument("--ico-sizes", type=parse_sizes, default=DEFAULT_ICO_SIZES)
    parser.add_argument("--supersample", type=int, default=4)
    parser.add_argument("--preview", action="store_true", help="Generate a light/dark small-size preview PNG.")
    args = parser.parse_args()

    if args.supersample < 1:
        parser.error("--supersample must be >= 1")
    if args.radius_ratio <= 0:
        parser.error("--radius-ratio must be > 0")

    try:
        build(args)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
