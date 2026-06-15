"""Compliant social caption builder (Fase 1).

One caption per (language, platform). Every caption opens with the affiliate
disclosure so it is visible before any "more" truncation, then a short product
pitch, the platform-correct call to action, and relevant hashtags. No em-dash
(site rule). Stdlib only.
"""
from social_common import (
    DISCLOSURE_TAG,
    currency_code,
    disclosure_caption,
    format_price,
    load_i18n,
    product_url,
    strip_em_dash,
)

# CTA copy per platform per language. IG/TikTok cannot use clickable links in
# the caption body, so they point to the bio; FB/X allow a direct link.
_CTA_BIO = {
    "en": "Shop it - link in bio",
    "it": "Scoprilo - link in bio",
    "es": "Consiguelo - link en la bio",
    "de": "Jetzt sichern - Link in Bio",
    "fr": "A decouvrir - lien en bio",
}
_CTA_LINK = {
    "en": "Shop it here:",
    "it": "Scoprilo qui:",
    "es": "Consiguelo aqui:",
    "de": "Jetzt hier sichern:",
    "fr": "A decouvrir ici:",
}

# Discount lead-in.
_DEAL = {
    "en": "Today's deal",
    "it": "Offerta di oggi",
    "es": "Oferta de hoy",
    "de": "Angebot des Tages",
    "fr": "Offre du jour",
}

_HASHTAGS = {
    "en": ["#aliexpress", "#deals", "#techfinds", "#gadgets"],
    "it": ["#aliexpress", "#offerte", "#sconti", "#gadget"],
    "es": ["#aliexpress", "#ofertas", "#descuentos", "#gadgets"],
    "de": ["#aliexpress", "#angebote", "#schnaeppchen", "#gadgets"],
    "fr": ["#aliexpress", "#bonsplans", "#promo", "#gadgets"],
}

# Platforms whose CTA must be "link in bio" (no clickable caption links).
BIO_PLATFORMS = {"instagram", "tiktok"}
# Platforms that accept a direct link in the caption body.
LINK_PLATFORMS = {"facebook", "x"}
PLATFORMS = sorted(BIO_PLATFORMS | LINK_PLATFORMS)


def build_caption(product: dict, lang: str, platform: str, config: dict,
                  site_url: str) -> str:
    """Return a compliant caption string for one language+platform."""
    lang = lang if lang in DISCLOSURE_TAG else "en"
    platform = platform.lower()
    T = load_i18n(lang)

    title = strip_em_dash(product.get("title", "")).strip()
    # Keep the title short for a punchy caption.
    if len(title) > 80:
        title = title[:77].rstrip() + "..."

    price = format_price(product.get("price"), T, config)
    disc = int(product.get("discount_pct") or 0)
    url = product_url(product, lang, site_url)

    lines = []
    # 1. Disclosure first, always visible.
    lines.append(disclosure_caption(lang))
    lines.append("")

    # 2. Product pitch.
    deal = f"{_DEAL[lang]}: {title}"
    lines.append(strip_em_dash(deal))
    if price:
        price_line = price if not disc else f"{price} (-{disc}%)"
        lines.append(price_line)
    lines.append("")

    # 3. Platform-correct CTA.
    if platform in BIO_PLATFORMS:
        lines.append(_CTA_BIO[lang])
    else:
        lines.append(f"{_CTA_LINK[lang]} {url}")
    lines.append("")

    # 4. Hashtags (disclosure tag first, then niche tags).
    tags = [DISCLOSURE_TAG[lang]] + _HASHTAGS.get(lang, _HASHTAGS["en"])
    cat = product.get("category")
    if cat and f"#{cat.replace('-', '')}" not in tags:
        tags.append(f"#{cat.replace('-', '')}")
    lines.append(" ".join(tags))

    return strip_em_dash("\n".join(lines)).strip()


def build_all_captions(product: dict, lang: str, config: dict,
                       site_url: str) -> dict:
    """All platform captions for one language. Keyed by platform."""
    return {
        platform: build_caption(product, lang, platform, config, site_url)
        for platform in PLATFORMS
    }
