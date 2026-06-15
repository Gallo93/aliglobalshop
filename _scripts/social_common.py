"""Shared helpers for the social video pipeline (Fase 1).

Loads catalog products, localizes prices the same way build.py does, and builds
the affiliate disclosure strings that must stay compliant across EN/IT/ES/DE/FR.
Kept dependency-free (stdlib only) so every social script can import it without
pulling in Pillow/ffmpeg.
"""
import html
import json
import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "_data"
PRODUCTS_DIR = DATA_DIR / "products"
I18N_DIR = DATA_DIR / "i18n"
CONFIG_PATH = DATA_DIR / "config.json"

LANGS = ["en", "it", "es", "de", "fr"]
NICHES = ["electronics", "smart-home", "sport", "gadgets"]

# Mirrors build.py / translate_content._DEFAULT_FX_RATES.
_DEFAULT_FX_RATES = {"EUR": 0.92}

SITE_URL_DEFAULT = "https://aliglobalshop.net"


def load_json(path: Path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def load_config() -> dict:
    return load_json(CONFIG_PATH, default={}) or {}


def _deep_merge(base: dict, overlay: dict) -> dict:
    out = dict(base)
    for k, v in (overlay or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_i18n(lang: str) -> dict:
    """Same deep-merge-on-en semantics as build.load_i18n."""
    base = load_json(I18N_DIR / "en.json", default={}) or {}
    if lang == "en":
        return base
    overlay = load_json(I18N_DIR / f"{lang}.json", default={}) or {}
    return _deep_merge(base, overlay)


def currency_symbol(T: dict) -> str:
    # i18n stores the HTML entity (&euro;); video/caption text needs the glyph.
    sym = T.get("_meta", {}).get("currency_symbol", "$")
    return html.unescape(sym)


def currency_code(T: dict) -> str:
    return T.get("_meta", {}).get("currency", "USD")


def resolve_fx_rate(config: dict, target_currency: str):
    """env FX_RATE_<CUR> > config fx_rates > built-in default. None disables it.
    Mirrors build._resolve_fx_rate so social prices match the site."""
    if not target_currency or target_currency == "USD":
        return None
    env_key = f"FX_RATE_{target_currency.upper()}"
    if os.getenv(env_key):
        try:
            return float(os.getenv(env_key))
        except (TypeError, ValueError):
            pass
    rates = (config or {}).get("fx_rates", {}) or {}
    if target_currency in rates:
        try:
            return float(rates[target_currency])
        except (TypeError, ValueError):
            pass
    return _DEFAULT_FX_RATES.get(target_currency)


def format_price(value, T: dict, config: dict | None = None) -> str:
    """Localized price glyph string for overlays/captions.

    USD (EN) keeps "$<value>"; EUR locales convert from the USD catalog value
    using the fx rate and render "<value> €" with a comma decimal, matching
    build.format_price output (sans HTML entity).
    """
    sym = currency_symbol(T)
    code = currency_code(T)
    if value is None or value == "":
        return ""
    if code == "USD":
        return f"{sym}{value}"
    try:
        usd = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return f"{sym}{value}"
    fx = resolve_fx_rate(config or {}, code)
    amount = round(usd * fx, 2) if fx else usd
    formatted = f"{amount:.2f}".replace(".", ",")
    return f"{formatted} {sym}"


def product_url(product: dict, lang: str, site_url: str) -> str:
    cat = product.get("category", "")
    slug = product.get("slug", "")
    return f"{site_url}/{lang}/{cat}/{slug}/"


# --- catalog ----------------------------------------------------------------

def _products_from_file(path: Path) -> list:
    data = load_json(path, default={}) or {}
    if isinstance(data, dict):
        return data.get("products", []) or []
    if isinstance(data, list):
        return data
    return []


def load_catalog(lang: str = "en") -> list:
    """All products for a language, flattened across niches (+ _article)."""
    out = []
    lang_dir = PRODUCTS_DIR / lang
    if not lang_dir.is_dir():
        return out
    for niche in NICHES:
        out.extend(_products_from_file(lang_dir / f"{niche}.json"))
    article_dir = lang_dir / "_article"
    if article_dir.is_dir():
        for jf in sorted(article_dir.glob("*.json")):
            out.extend(_products_from_file(jf))
    return out


def pick_product(lang: str = "en", slug: str | None = None) -> dict | None:
    """Pick a product by slug, else the best-discounted in-stock candidate."""
    catalog = load_catalog(lang)
    if not catalog:
        return None
    if slug:
        for p in catalog:
            if p.get("slug") == slug:
                return p
        return None

    def score(p):
        return (
            int(p.get("discount_pct") or 0),
            float(p.get("rating") or 0),
            int(p.get("reviews_count") or 0),
        )

    valid = [p for p in catalog if p.get("image_url") and p.get("title")]
    if not valid:
        return None
    return max(valid, key=score)


# --- disclosure / compliance ------------------------------------------------

# FTC/AGCM-style transparency: a visible advertising tag plus a plain-language
# "affiliate link" note. Shown burned into the video AND opening the caption.
DISCLOSURE_TAG = {
    "en": "#ad",
    "it": "#adv",
    "es": "#publicidad",
    "de": "#werbung",
    "fr": "#pub",
}

DISCLOSURE_NOTE = {
    "en": "affiliate link",
    "it": "link affiliato",
    "es": "enlace de afiliado",
    "de": "Affiliate-Link",
    "fr": "lien affilie",
}

# Longer transparency line for captions (no em-dash, ASCII-safe).
DISCLOSURE_LONG = {
    "en": "Affiliate link: we may earn a small commission at no extra cost to you.",
    "it": "Link affiliato: potremmo guadagnare una piccola commissione senza costi aggiuntivi per te.",
    "es": "Enlace de afiliado: podemos ganar una pequena comision sin coste adicional para ti.",
    "de": "Affiliate-Link: Wir verdienen moeglicherweise eine kleine Provision, ohne zusaetzliche Kosten fuer dich.",
    "fr": "Lien affilie: nous pourrions toucher une petite commission, sans cout supplementaire pour vous.",
}


def disclosure_overlay(lang: str) -> str:
    """Short always-on overlay line burned into the video."""
    lang = lang if lang in DISCLOSURE_TAG else "en"
    return f"{DISCLOSURE_TAG[lang]} - {DISCLOSURE_NOTE[lang]}"


def disclosure_caption(lang: str) -> str:
    """Disclosure that opens every caption (placed first for visibility)."""
    lang = lang if lang in DISCLOSURE_TAG else "en"
    return f"{DISCLOSURE_TAG[lang]} {DISCLOSURE_LONG[lang]}"


def strip_em_dash(text: str) -> str:
    """Site rule: no em-dash in visible text."""
    return (text or "").replace("—", "-").replace("–", "-")
