"""Product Spotlight social video generator (Fase 1, Strada A).

Renders a silent vertical 1080x1920 (9:16) MP4 from a catalog product using
Pillow (frames) + ffmpeg (encode). The affiliate disclosure is burned in and
visible for the full clip. No audio (music needs a commercial licence, added
later). Output goes to out/social/ (not committed). Also writes the matching
compliant caption(s).

Usage:
    python _scripts/generate_social_video.py --lang it
    python _scripts/generate_social_video.py --slug <slug> --lang en
    python _scripts/generate_social_video.py --lang de --no-video   # caption only

Requires ffmpeg on PATH and Pillow. In DRY_RUN (default) nothing is published;
the image is downloaded if reachable, otherwise a generated placeholder is used.
"""
import argparse
import io
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:  # pragma: no cover
    print("[error] Pillow not installed. Run: pip install Pillow", file=sys.stderr)
    raise

# Allow running as a script from anywhere.
sys.path.insert(0, str(Path(__file__).parent))
from social_common import (  # noqa: E402
    BASE_DIR,
    SITE_URL_DEFAULT,
    currency_code,
    disclosure_overlay,
    format_price,
    load_config,
    load_i18n,
    pick_product,
    strip_em_dash,
)
from social_caption import build_all_captions  # noqa: E402

WIDTH, HEIGHT = 1080, 1920
FPS = 30
DURATION_S = 22
OUT_DIR = BASE_DIR / "out" / "social"
FONT_DIR = BASE_DIR / "assets" / "fonts"

# Brand palette (dark vertical gradient, warm accent for price/CTA).
BG_TOP = (17, 24, 39)        # slate-900
BG_BOTTOM = (30, 41, 59)     # slate-800
ACCENT = (249, 115, 22)      # orange-500
TEXT = (248, 250, 252)       # near-white
MUTED = (148, 163, 184)      # slate-400

# Localized CTA burned into the video. Neutral and true on EVERY platform: the
# same MP4 is published to IG/TikTok (link in bio) and FB/X (link in caption),
# so the overlay must not claim "link in bio" (false on FB/X). The clickable
# CTA lives in the per-platform caption (social_caption.py); see SOCIAL_README.
_CTA = {
    "en": "Shop now", "it": "Scoprilo ora", "es": "Consiguelo ya",
    "de": "Jetzt entdecken", "fr": "A decouvrir",
}
_DISCOUNT_BADGE = {
    "en": "OFF", "it": "SCONTO", "es": "DTO", "de": "RABATT", "fr": "REMISE",
}


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load the bundled free font; fall back to PIL default if missing."""
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    candidates = [FONT_DIR / name]
    # Pillow ships DejaVu; use it as a fallback source so CI never breaks.
    try:
        import PIL
        pil_fonts = Path(PIL.__file__).parent / "fonts"
        candidates.append(pil_fonts / name)
    except Exception:
        pass
    for c in candidates:
        try:
            return ImageFont.truetype(str(c), size)
        except (OSError, ValueError):
            continue
    return ImageFont.load_default()


def _download_image(url: str):
    if not url:
        return None
    try:
        import requests
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return Image.open(io.BytesIO(resp.content)).convert("RGB")
    except Exception as exc:
        print(f"[warn] image download failed ({exc}); using placeholder")
        return None


def _placeholder_image(title: str) -> Image.Image:
    img = Image.new("RGB", (900, 900), (51, 65, 85))
    d = ImageDraw.Draw(img)
    f = _font(46, bold=True)
    word = (title.split() or ["AliGlobalShop"])[0][:14]
    bbox = d.textbbox((0, 0), word, font=f)
    d.text(((900 - (bbox[2] - bbox[0])) / 2, 420), word, font=f, fill=MUTED)
    return img


def _gradient_bg() -> Image.Image:
    base = Image.new("RGB", (WIDTH, HEIGHT), BG_TOP)
    top = Image.new("RGB", (1, HEIGHT))
    for y in range(HEIGHT):
        t = y / (HEIGHT - 1)
        top.putpixel((0, y), tuple(
            int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3)
        ))
    return top.resize((WIDTH, HEIGHT))


def _wrap(draw, text, font, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _rounded(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def _compose_frame(bg, product_img, T, lang, product, config, progress):
    """One frame at animation position `progress` in [0,1]."""
    frame = bg.copy()
    draw = ImageDraw.Draw(frame, "RGBA")

    # Ken-burns zoom on the product image (1.0 -> 1.08), centered in a card.
    card_w, card_h = 860, 860
    card_x = (WIDTH - card_w) // 2
    card_y = 360
    zoom = 1.0 + 0.08 * progress
    pw, ph = product_img.size
    scale = max(card_w / pw, card_h / ph) * zoom
    rw, rh = int(pw * scale), int(ph * scale)
    pimg = product_img.resize((rw, rh))
    crop_x = (rw - card_w) // 2
    crop_y = (rh - card_h) // 2
    pimg = pimg.crop((crop_x, crop_y, crop_x + card_w, crop_y + card_h))

    mask = Image.new("L", (card_w, card_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, card_w, card_h), radius=48, fill=255)
    frame.paste(pimg, (card_x, card_y), mask)

    # Discount badge.
    disc = int(product.get("discount_pct") or 0)
    if disc:
        bf = _font(52, bold=True)
        label = f"-{disc}% {_DISCOUNT_BADGE.get(lang, 'OFF')}"
        tw = draw.textlength(label, font=bf)
        bx, by = card_x + 24, card_y + 24
        _rounded(draw, (bx, by, bx + tw + 48, by + 84), 20, ACCENT)
        draw.text((bx + 24, by + 14), label, font=bf, fill=(17, 24, 39))

    # Title (wrapped, max 3 lines).
    tf = _font(58, bold=True)
    title = strip_em_dash(product.get("title", "")).strip()
    lines = _wrap(draw, title, tf, WIDTH - 140)[:3]
    ty = 1260
    for ln in lines:
        draw.text((70, ty), ln, font=tf, fill=TEXT)
        ty += 70

    # Price.
    pf = _font(96, bold=True)
    price = format_price(product.get("price"), T, config)
    if price:
        draw.text((70, ty + 20), price, font=pf, fill=ACCENT)
        orig = product.get("original_price")
        if orig:
            of = _font(48)
            orig_str = format_price(orig, T, config)
            ox = 70 + draw.textlength(price, font=pf) + 30
            draw.text((ox, ty + 60), orig_str, font=of, fill=MUTED)
            # strike-through
            ow = draw.textlength(orig_str, font=of)
            draw.line((ox, ty + 88, ox + ow, ty + 88), fill=MUTED, width=4)

    # CTA pill (fades/pulses with progress).
    cf = _font(50, bold=True)
    cta = _CTA.get(lang, _CTA["en"])
    cw = draw.textlength(cta, font=cf)
    pulse = int(20 * (0.5 + 0.5 * math.sin(progress * math.pi * 4)))
    cx, cy = 70, 1640
    _rounded(draw, (cx, cy, cx + cw + 80 + pulse, cy + 96), 48,
             ACCENT + (255,))
    draw.text((cx + 40 + pulse // 2, cy + 22), cta, font=cf, fill=(17, 24, 39))

    # ALWAYS-ON disclosure bar (top), high contrast, full width.
    df = _font(40, bold=True)
    disclosure = disclosure_overlay(lang)
    dw = draw.textlength(disclosure, font=df)
    _rounded(draw, (40, 60, 40 + dw + 64, 60 + 76), 18, (0, 0, 0, 200))
    draw.text((72, 78), disclosure, font=df, fill=(255, 255, 255))

    # Brand footer.
    ff = _font(34)
    draw.text((70, 1840), "aliglobalshop.net", font=ff, fill=MUTED)
    return frame


def generate_video(product, lang, config, site_url, make_video=True):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    T = load_i18n(lang)
    slug = product.get("slug", "product")
    stem = f"{slug}-{lang}"

    # Caption file (all platforms).
    captions = build_all_captions(product, lang, config, site_url)
    caption_path = OUT_DIR / f"{stem}.caption.txt"
    with open(caption_path, "w", encoding="utf-8") as f:
        for platform, text in captions.items():
            f.write(f"===== {platform.upper()} =====\n{text}\n\n")
    print(f"[ok] caption written: {caption_path}")

    if not make_video:
        return None, caption_path

    if not shutil.which("ffmpeg"):
        print("[error] ffmpeg not found on PATH. Skipping video.", file=sys.stderr)
        return None, caption_path

    product_img = _download_image(product.get("image_url")) or \
        _placeholder_image(product.get("title", ""))
    bg = _gradient_bg()

    total_frames = FPS * DURATION_S
    tmp = Path(tempfile.mkdtemp(prefix="social_frames_"))
    try:
        # Render unique frames only where the animation changes; ffmpeg reads
        # the full numbered sequence. Subsample to keep render fast (every 3rd).
        step = 3
        last = None
        for i in range(total_frames):
            if i % step == 0:
                progress = i / max(total_frames - 1, 1)
                last = _compose_frame(bg, product_img, T, lang, product, config, progress)
            last.save(tmp / f"f{i:04d}.png")
        out_path = OUT_DIR / f"{stem}.mp4"
        cmd = [
            "ffmpeg", "-y", "-framerate", str(FPS),
            "-i", str(tmp / "f%04d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-vf", "fade=in:0:15,fade=out:" + str(total_frames - 15) + ":15",
            "-movflags", "+faststart",
            str(out_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            print("[error] ffmpeg failed:\n" + proc.stderr[-1500:], file=sys.stderr)
            return None, caption_path
        print(f"[ok] video written: {out_path} ({out_path.stat().st_size // 1024} KB)")
        return out_path, caption_path
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description="Generate a Product Spotlight social video (DRY_RUN).")
    ap.add_argument("--lang", default="en", help="en|it|es|de|fr")
    ap.add_argument("--slug", default=None, help="product slug (default: best deal)")
    ap.add_argument("--no-video", action="store_true", help="caption only, skip MP4")
    args = ap.parse_args()

    config = load_config()
    site_url = config.get("site_url", SITE_URL_DEFAULT)
    product = pick_product(args.lang, args.slug)
    if not product:
        print(f"[error] no product found (lang={args.lang}, slug={args.slug})", file=sys.stderr)
        sys.exit(1)

    print(f"[info] product: {product.get('slug')} | {product.get('title', '')[:60]}")
    video, caption = generate_video(product, args.lang, config, site_url,
                                    make_video=not args.no_video)
    print("[done] DRY_RUN: nothing published. "
          f"video={'-' if not video else video.name} caption={caption.name}")


if __name__ == "__main__":
    main()
