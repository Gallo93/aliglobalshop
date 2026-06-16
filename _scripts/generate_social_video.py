"""Product Spotlight social video generator (Fase 2, Remotion engine).

Builds the data + caption for an animated vertical reel (9:16, 1080x1920, ~22s)
from a catalog product. The actual MP4 is now rendered by the Remotion project
in social/remotion/ (motion graphics), driven by a props file this script
emits: out/social/<slug>-<lang>.props.json.

Two engines:
  --engine remotion (default)  write the .props.json (+ caption). The workflow
                               then runs `npx remotion render ... --props=...`.
  --engine ffmpeg              legacy static Pillow+ffmpeg render kept as a
                               documented fallback (no Node needed). Animated
                               only in the crudest sense; prefer remotion.

The affiliate disclosure is always present (overlay in the reel, opening line in
the caption). No audio (music needs a commercial licence). Output goes to
out/social/ (gitignored). In DRY_RUN nothing is published.

Optional cinematic intro: when a Pexels b-roll clip is available (PEXELS_API_KEY
set), the first ~2.3s use it as a moving background behind the hook. Without a
key the existing animated intro is used (default, byte-compatible).

Usage:
    # props for Remotion (default) + caption
    python _scripts/generate_social_video.py --lang it
    python _scripts/generate_social_video.py --slug <slug> --lang en
    python _scripts/generate_social_video.py --lang de --no-video   # caption only
    # legacy static render
    python _scripts/generate_social_video.py --lang it --engine ffmpeg
"""
import argparse
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Allow running as a script from anywhere.
sys.path.insert(0, str(Path(__file__).parent))
from social_common import (  # noqa: E402
    BASE_DIR,
    SITE_URL_DEFAULT,
    disclosure_overlay,
    format_price,
    load_config,
    load_i18n,
    pick_product,
    strip_em_dash,
)
from social_caption import build_all_captions  # noqa: E402
from social_intro import fetch_intro_clip  # noqa: E402

WIDTH, HEIGHT = 1080, 1920
FPS = 30
DURATION_S = 22
OUT_DIR = BASE_DIR / "out" / "social"
FONT_DIR = BASE_DIR / "assets" / "fonts"
REMOTION_DIR = BASE_DIR / "social" / "remotion"

# Brand palette shared with the Remotion composition (DEFAULT_PROPS in
# social/remotion/src/types.ts). Hex here, RGB tuples for the ffmpeg fallback.
BRAND_COLORS = {
    "bgTop": "#111827",     # slate-900
    "bgBottom": "#1e293b",  # slate-800
    "accent": "#f97316",    # orange-500
    "text": "#f8fafc",      # near-white
    "muted": "#94a3b8",     # slate-400
}
BG_TOP = (17, 24, 39)
BG_BOTTOM = (30, 41, 59)
ACCENT = (249, 115, 22)
TEXT = (248, 250, 252)
MUTED = (148, 163, 184)

# Localized CTA burned into the reel. Neutral and true on EVERY platform (the
# same MP4 goes to IG/TikTok and FB/X), so it must not claim "link in bio".
_CTA = {
    "en": "Shop now", "it": "Scoprilo ora", "es": "Consiguelo ya",
    "de": "Jetzt entdecken", "fr": "A decouvrir",
}
_DISCOUNT_BADGE = {
    "en": "OFF", "it": "SCONTO", "es": "DTO", "de": "RABATT", "fr": "REMISE",
}

# Short localized feature lines synthesized from catalog signals (the catalog
# has no per-product feature list). Kept generic, true, ASCII-safe, no em-dash.
_FEAT_DISCOUNT = {
    "en": "Save {pct}% today", "it": "Risparmi il {pct}% oggi",
    "es": "Ahorra {pct}% hoy", "de": "{pct}% sparen", "fr": "{pct}% d'economie",
}
_FEAT_RATING = {
    "en": "Rated {r}/5", "it": "Valutato {r}/5", "es": "Valorado {r}/5",
    "de": "Bewertet {r}/5", "fr": "Note {r}/5",
}
_FEAT_REVIEWS = {
    "en": "{n} reviews", "it": "{n} recensioni", "es": "{n} resenas",
    "de": "{n} Bewertungen", "fr": "{n} avis",
}
_FEAT_SHIPPING = {
    "en": "Ships worldwide", "it": "Spedizione globale", "es": "Envio mundial",
    "de": "Weltweiter Versand", "fr": "Livraison mondiale",
}
_FEAT_QUALITY = {
    "en": "Top pick", "it": "Scelta top", "es": "Eleccion top",
    "de": "Top-Wahl", "fr": "Choix top",
}


def _build_features(product: dict, lang: str) -> list:
    """Up to 4 short, true bullet lines from the product's own signals."""
    lang = lang if lang in _CTA else "en"
    feats = []
    disc = int(product.get("discount_pct") or 0)
    if disc:
        feats.append(_FEAT_DISCOUNT[lang].format(pct=disc))
    rating = product.get("rating")
    try:
        if rating is not None and float(rating) > 0:
            feats.append(_FEAT_RATING[lang].format(r=f"{float(rating):.1f}"))
    except (TypeError, ValueError):
        pass
    reviews = int(product.get("reviews_count") or 0)
    if reviews >= 10:
        feats.append(_FEAT_REVIEWS[lang].format(n=reviews))
    feats.append(_FEAT_SHIPPING[lang])
    if len(feats) < 4:
        feats.append(_FEAT_QUALITY[lang])
    return [strip_em_dash(f) for f in feats[:4]]


def build_props(product: dict, lang: str, config: dict,
                intro_clip: str | None = None) -> dict:
    """Assemble the typed props the Remotion ProductSpotlight expects.

    Mirrors social/remotion/src/types.ts (ProductSpotlightProps). Prices are
    localized here so the reel matches the site (same format_price as build.py).
    `intro_clip` is the staticFile-relative name of the optional b-roll clip
    (e.g. "intro/intro-sport-12345.mp4") or None to keep the animated intro.
    """
    T = load_i18n(lang)
    price = format_price(product.get("price"), T, config)
    orig = product.get("original_price")
    orig_fmt = format_price(orig, T, config) if orig else None
    disc = int(product.get("discount_pct") or 0)
    title = strip_em_dash(product.get("title", "")).strip()
    return {
        "productName": title,
        "priceFormatted": price,
        "originalPriceFormatted": orig_fmt,
        "discountPct": disc,
        "imageUrl": product.get("image_url") or None,
        "features": _build_features(product, lang),
        "ctaText": _CTA.get(lang, _CTA["en"]),
        "discountBadgeLabel": _DISCOUNT_BADGE.get(lang, "OFF"),
        "disclosureText": disclosure_overlay(lang),
        "brandUrl": "aliglobalshop.net",
        "lang": lang if lang in _CTA else "en",
        "brandColors": BRAND_COLORS,
        "introClip": intro_clip,
    }


def _prepare_intro_clip(product: dict, out_dir: Path) -> str | None:
    """Fetch an optional Pexels b-roll clip and stage it for Remotion.

    Downloads into out_dir (gitignored), then copies it into the Remotion public
    dir so staticFile() can resolve it, and returns the staticFile-relative name
    ("intro/<file>"). Returns None when no clip is available (no key / mock /
    network error) so the composition falls back to the animated intro. Never
    raises: any staging error degrades to None.
    """
    niche = (product.get("category") or "").strip()
    clip_path = fetch_intro_clip(niche, out_dir)
    if not clip_path:
        return None
    try:
        public_intro = REMOTION_DIR / "public" / "intro"
        public_intro.mkdir(parents=True, exist_ok=True)
        dst = public_intro / Path(clip_path).name
        shutil.copyfile(clip_path, dst)
        # staticFile() resolves relative to social/remotion/public/.
        return f"intro/{dst.name}"
    except OSError as exc:
        print(f"[warn] could not stage intro clip for Remotion ({exc}); "
              "using animated fallback.")
        return None


# --- legacy ffmpeg fallback (static) ----------------------------------------

def _font(size: int, bold: bool = False):
    from PIL import ImageFont
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    candidates = [FONT_DIR / name]
    try:
        import PIL
        candidates.append(Path(PIL.__file__).parent / "fonts" / name)
    except Exception:
        pass
    for c in candidates:
        try:
            return ImageFont.truetype(str(c), size)
        except (OSError, ValueError):
            continue
    return ImageFont.load_default()


def _download_image(url: str):
    from PIL import Image
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


def _placeholder_image(title: str):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (900, 900), (51, 65, 85))
    d = ImageDraw.Draw(img)
    f = _font(46, bold=True)
    word = (title.split() or ["AliGlobalShop"])[0][:14]
    bbox = d.textbbox((0, 0), word, font=f)
    d.text(((900 - (bbox[2] - bbox[0])) / 2, 420), word, font=f, fill=MUTED)
    return img


def _gradient_bg():
    from PIL import Image
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
    from PIL import Image, ImageDraw
    frame = bg.copy()
    draw = ImageDraw.Draw(frame, "RGBA")
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

    disc = int(product.get("discount_pct") or 0)
    if disc:
        bf = _font(52, bold=True)
        label = f"-{disc}% {_DISCOUNT_BADGE.get(lang, 'OFF')}"
        tw = draw.textlength(label, font=bf)
        bx, by = card_x + 24, card_y + 24
        _rounded(draw, (bx, by, bx + tw + 48, by + 84), 20, ACCENT)
        draw.text((bx + 24, by + 14), label, font=bf, fill=(17, 24, 39))

    tf = _font(58, bold=True)
    title = strip_em_dash(product.get("title", "")).strip()
    lines = _wrap(draw, title, tf, WIDTH - 140)[:3]
    ty = 1260
    for ln in lines:
        draw.text((70, ty), ln, font=tf, fill=TEXT)
        ty += 70

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
            ow = draw.textlength(orig_str, font=of)
            draw.line((ox, ty + 88, ox + ow, ty + 88), fill=MUTED, width=4)

    cf = _font(50, bold=True)
    cta = _CTA.get(lang, _CTA["en"])
    cw = draw.textlength(cta, font=cf)
    pulse = int(20 * (0.5 + 0.5 * math.sin(progress * math.pi * 4)))
    cx, cy = 70, 1640
    _rounded(draw, (cx, cy, cx + cw + 80 + pulse, cy + 96), 48, ACCENT + (255,))
    draw.text((cx + 40 + pulse // 2, cy + 22), cta, font=cf, fill=(17, 24, 39))

    df = _font(40, bold=True)
    disclosure = disclosure_overlay(lang)
    dw = draw.textlength(disclosure, font=df)
    _rounded(draw, (40, 60, 40 + dw + 64, 60 + 76), 18, (0, 0, 0, 200))
    draw.text((72, 78), disclosure, font=df, fill=(255, 255, 255))

    ff = _font(34)
    draw.text((70, 1840), "aliglobalshop.net", font=ff, fill=MUTED)
    return frame


def _render_ffmpeg(product, lang, config):
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print("[error] Pillow not installed (needed for --engine ffmpeg).",
              file=sys.stderr)
        return None
    if not shutil.which("ffmpeg"):
        print("[error] ffmpeg not found on PATH. Skipping video.", file=sys.stderr)
        return None
    T = load_i18n(lang)
    slug = product.get("slug", "product")
    stem = f"{slug}-{lang}"
    product_img = _download_image(product.get("image_url")) or \
        _placeholder_image(product.get("title", ""))
    bg = _gradient_bg()
    total_frames = FPS * DURATION_S
    tmp = Path(tempfile.mkdtemp(prefix="social_frames_"))
    try:
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
            return None
        print(f"[ok] video written: {out_path} ({out_path.stat().st_size // 1024} KB)")
        return out_path
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- main --------------------------------------------------------------------

def _bundle_fonts(remotion_dir: Path) -> None:
    """Copy the shared DejaVu fonts into the Remotion public dir (build-time).

    The reel loads them via staticFile("fonts/..."); we keep the source of truth
    in assets/fonts/ instead of duplicating binaries in the Remotion project.
    """
    dst = remotion_dir / "public" / "fonts"
    dst.mkdir(parents=True, exist_ok=True)
    for name in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"):
        src = FONT_DIR / name
        if src.is_file():
            try:
                shutil.copyfile(src, dst / name)
            except OSError as exc:
                print(f"[warn] could not bundle font {name}: {exc}")


def generate(product, lang, config, site_url, engine="remotion", make_video=True):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = product.get("slug", "product")
    stem = f"{slug}-{lang}"

    # Caption file (all platforms) - same as Fase 1.
    captions = build_all_captions(product, lang, config, site_url)
    caption_path = OUT_DIR / f"{stem}.caption.txt"
    with open(caption_path, "w", encoding="utf-8") as f:
        for platform, text in captions.items():
            f.write(f"===== {platform.upper()} =====\n{text}\n\n")
    print(f"[ok] caption written: {caption_path}")

    # Optional Pexels b-roll intro clip (None -> animated intro fallback).
    intro_clip = _prepare_intro_clip(product, OUT_DIR)

    # Props file for Remotion (the data contract for the animated reel).
    props = build_props(product, lang, config, intro_clip=intro_clip)
    props_path = OUT_DIR / f"{stem}.props.json"
    with open(props_path, "w", encoding="utf-8") as f:
        json.dump(props, f, ensure_ascii=False, indent=2)
    print(f"[ok] props written: {props_path}")

    if not make_video:
        return None, caption_path, props_path

    if engine == "ffmpeg":
        video = _render_ffmpeg(product, lang, config)
        return video, caption_path, props_path

    # engine == remotion: the MP4 is produced by the Remotion CLI using the
    # props file above. Render here only if Node + the project deps are present
    # (local convenience); CI runs the render in its own step.
    remotion_dir = BASE_DIR / "social" / "remotion"
    out_mp4 = OUT_DIR / f"{stem}.mp4"
    if shutil.which("npx") and (remotion_dir / "node_modules").is_dir():
        _bundle_fonts(remotion_dir)
        cmd = [
            "npx", "remotion", "render", "ProductSpotlight", str(out_mp4),
            f"--props={props_path}",
        ]
        # shell=True on Windows so the npx.cmd shim is resolved.
        proc = subprocess.run(cmd, cwd=str(remotion_dir),
                              shell=(os.name == "nt"))
        if proc.returncode == 0 and out_mp4.is_file():
            print(f"[ok] reel rendered: {out_mp4}")
            return out_mp4, caption_path, props_path
        print("[warn] remotion render failed locally; props file is ready for CI.",
              file=sys.stderr)
        return None, caption_path, props_path

    print("[info] Remotion not installed locally; props file is ready. "
          "Run the render in social/remotion (see SOCIAL_README).")
    return None, caption_path, props_path


def main():
    ap = argparse.ArgumentParser(
        description="Generate Product Spotlight reel data + caption (DRY_RUN).")
    ap.add_argument("--lang", default="en", help="en|it|es|de|fr")
    ap.add_argument("--slug", default=None, help="product slug (default: best deal)")
    ap.add_argument("--engine", default="remotion", choices=["remotion", "ffmpeg"],
                    help="remotion (animated reel, default) | ffmpeg (legacy static)")
    ap.add_argument("--no-video", action="store_true", help="caption + props only")
    args = ap.parse_args()

    config = load_config()
    site_url = config.get("site_url", SITE_URL_DEFAULT)
    product = pick_product(args.lang, args.slug)
    if not product:
        print(f"[error] no product found (lang={args.lang}, slug={args.slug})",
              file=sys.stderr)
        sys.exit(1)

    print(f"[info] product: {product.get('slug')} | {product.get('title', '')[:60]}")
    print(f"[info] engine: {args.engine}")
    video, caption, props = generate(
        product, args.lang, config, site_url,
        engine=args.engine, make_video=not args.no_video)
    print("[done] DRY_RUN: nothing published. "
          f"video={'-' if not video else video.name} "
          f"caption={caption.name} props={props.name}")


if __name__ == "__main__":
    main()
