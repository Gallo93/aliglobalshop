"""
Static site generator for AliGlobalShop.

Reads JSON in _data/ + templates in _templates/, writes HTML per language.
UI strings live in _data/i18n/<lang>.json (en.json = source of truth, exact
current strings; other languages overlay on top with EN fallback).
Uses str.replace for {{KEY}} placeholders, no Jinja.
"""
import html
import json
import re
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "_data"
TEMPLATES_DIR = BASE_DIR / "_templates"
I18N_DIR = DATA_DIR / "i18n"
CONFIG_PATH = DATA_DIR / "config.json"

SITE_TITLE = "AliGlobalShop"
SITE_DESCRIPTION = (
    "Curated AliExpress deals, live flash sales and working coupons, updated every day."
)
DEFAULT_SHIPPING_DAYS = "7-25"
DEFAULT_OG_IMAGE_PATH = "/assets/img/og-default.jpg"

# Flag emoji + short code per language, used by the nav language switcher.
# A language with no entry here falls back to its i18n _meta locale_name.
LANG_FLAGS = {
    "en": "&#127468;&#127463;",
    "it": "&#127470;&#127481;",
    "es": "&#127466;&#127480;",
    "de": "&#127465;&#127466;",
    "fr": "&#127467;&#127479;",
}

CATEGORY_PARTICLES = {
    "electronics": "electric",
    "smart-home": "glow",
    "sport": "streak",
    "gadgets": "glitch",
}

_SPECIFIC_PRODUCT_TERMS = [
    (re.compile(r'\bearbuds?\b|\bearphone\b|\bheadphone\b|\bheadset\b', re.I),
     ["earbuds", "earphone", "headphone", "headset", "airpod"]),
    (re.compile(r'\bvacuum\b', re.I),
     ["vacuum"]),
    (re.compile(r'\bbulbs?\b', re.I),
     ["bulb"]),
    (re.compile(r'\bsmartwatche?s?\b|\bsmart\s+watch\b', re.I),
     ["smartwatch", "smart watch"]),
    (re.compile(r'\bhome\s+gym\b|\bgym\s+equipment\b|\bdumbbell\b|\btreadmill\b', re.I),
     ["gym", "dumbbell", "treadmill", "barbell", "kettlebell"]),
]

STATIC_PAGES = ["privacy", "about", "contact"]

LOW_PRIORITY_PAGES = {"privacy", "about", "contact"}


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"[warn] cannot parse {path}: {exc}")
        return default


def _deep_merge(base: dict, overlay: dict) -> dict:
    out = dict(base)
    for key, value in (overlay or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_i18n(lang: str) -> dict:
    base = load_json(I18N_DIR / "en.json", default={})
    if lang == "en":
        return base
    overlay = load_json(I18N_DIR / f"{lang}.json", default={})
    return _deep_merge(base, overlay)


def load_template(name: str) -> str:
    with open(TEMPLATES_DIR / name, encoding="utf-8") as f:
        return f.read()


def render(template_str: str, context: dict) -> str:
    out = template_str
    for key, value in context.items():
        out = out.replace("{{" + key + "}}", "" if value is None else str(value))
    return out


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def esc(value) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def short_title(title: str, limit: int = 60) -> str:
    if not title:
        return ""
    if len(title) <= limit:
        return title
    return title[: limit - 1].rstrip() + "…"


def alt_text(title: str, limit: int = 125) -> str:
    if not title:
        return ""
    if len(title) <= limit:
        return title
    cut = title[:limit].rstrip()
    if " " in cut:
        cut = cut[: cut.rfind(" ")].rstrip()
    return cut


def _price_val(product: dict) -> float:
    try:
        return float(product.get("price", 9999) or 9999)
    except (TypeError, ValueError):
        return 9999.0


def _extract_price_ceiling(text: str):
    m = re.search(r'\bunder\s+\$?(\d+(?:\.\d+)?)', text, re.IGNORECASE)
    if m:
        return float(m.group(1))
    return None


def category_name(T: dict, slug: str) -> str:
    return T.get("category_names", {}).get(slug, slug.title())


def currency_symbol(T: dict) -> str:
    return T.get("_meta", {}).get("currency_symbol", "$")


def currency_code(T: dict) -> str:
    return T.get("_meta", {}).get("currency", "USD")


def format_price(value, T: dict) -> str:
    """Format a price for display in the build language.

    USD (EN) keeps the exact legacy rendering "$<value>" (symbol before, the
    value's str() unchanged) so EN output stays byte-identical. EUR locales
    render "<value> &euro;" with a comma decimal separator and two decimals
    (e.g. 11.56 -> "11,56 &euro;", 42.8 -> "42,80 &euro;"). Empty/None and
    non-numeric values keep the legacy "<symbol><value>" form.
    """
    sym = currency_symbol(T)
    code = currency_code(T)
    if value is None or value == "":
        return esc(value)
    if code == "USD":
        return f"{sym}{esc(value)}"
    try:
        amount = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return f"{sym}{esc(value)}"
    formatted = f"{amount:.2f}".replace(".", ",")
    return f"{formatted} {sym}"


def _format_price_plain(value, T: dict) -> str:
    """Like format_price but with the literal currency symbol (e.g. '€') rather
    than its HTML entity, for use in raw text that the caller escapes later."""
    formatted = format_price(value, T)
    return formatted.replace("&euro;", "€")


def meta_desc_from_product(product: dict, T: dict) -> str:
    base = product.get("title", "")
    disc = product.get("discount_pct") or 0
    p = T.get("product", {})
    only = p.get("meta_only", "only")
    on_ali = p.get("meta_on_aliexpress", "on AliExpress")
    text = f"{base}: {only} {_format_price_plain(product.get('price'), T)} {on_ali}"
    if disc:
        text += f" (-{disc}%)"
    return short_title(text, 155)


def product_card_html(product: dict, category_slug: str, site_url: str, lang: str, T: dict) -> str:
    href = f"{site_url}/{lang}/{category_slug}/{esc(product.get('slug', ''))}/"
    img = esc(product.get("image_url", ""))
    title = esc(product.get("title", ""))
    alt = esc(alt_text(product.get("title", "")))
    price = format_price(product.get("price", ""), T)
    original = format_price(product.get("original_price", ""), T)
    disc = product.get("discount_pct") or 0
    rating = product.get("rating") or 0
    reviews = product.get("reviews_count") or 0
    ui = T.get("ui", {})
    disc_html = f'<span class="price--off">-{int(disc)}%</span>' if disc else ""
    return (
        '<article class="product-card">'
        f'<a href="{href}" class="product-card__img">'
        f'<img src="{img}" alt="{alt}" width="300" height="300" loading="lazy" decoding="async"></a>'
        '<div class="product-card__body">'
        f'<h3 class="product-card__title"><a href="{href}">{title}</a></h3>'
        f'<div class="product-card__price"><span class="price">{price}</span>'
        f'<span class="price--old">{original}</span>{disc_html}</div>'
        f'<p class="product-card__meta">{ui.get("card_rating", "Rating")}: {rating}/5 · {reviews} {ui.get("card_reviews", "reviews")}</p>'
        f'<a class="btn-cta product-card__cta" href="{href}">{ui.get("card_see_deal", "See deal &#8594;")}</a>'
        "</div></article>"
    )


def deal_card_html(deal: dict, site_url: str, lang: str, T: dict) -> str:
    category_slug = deal.get("category", "")
    ui = T.get("ui", {})
    if category_slug:
        href = f"{site_url}/{lang}/{category_slug}/{esc(deal.get('slug', ''))}/"
        link_rel = ""
    else:
        href = esc(deal.get("affiliate_url", f"{site_url}/{lang}/flash-sale/"))
        link_rel = ' rel="nofollow sponsored noopener"'
    img = esc(deal.get("image_url", ""))
    title = esc(deal.get("title", ""))
    alt = esc(alt_text(deal.get("title", "")))
    price = format_price(deal.get("price", ""), T)
    original = format_price(deal.get("original_price", ""), T)
    disc = deal.get("discount_pct") or 0
    expires = esc(deal.get("expires_at", ""))
    disc_html = f'<span class="price--off">-{int(disc)}%</span>' if disc else ""
    countdown = f'<span data-expires="{expires}"></span>' if expires else ""
    return (
        '<article class="product-card">'
        f'<a href="{href}"{link_rel} class="product-card__img">'
        f'<img src="{img}" alt="{alt}" width="300" height="300" loading="lazy" decoding="async"></a>'
        '<div class="product-card__body">'
        f'<h3 class="product-card__title"><a href="{href}"{link_rel}>{title}</a></h3>'
        f'<div class="product-card__price"><span class="price">{price}</span>'
        f'<span class="price--old">{original}</span>{disc_html}</div>'
        f'<p class="product-card__meta">{ui.get("card_ends_in", "Ends in")}: {countdown}</p>'
        f'<a class="btn-cta product-card__cta" href="{href}"{link_rel}>{ui.get("card_grab_it", "Grab it &#8594;")}</a>'
        "</div></article>"
    )


def coupon_card_html(coupon: dict, site_url: str, lang: str, T: dict) -> str:
    ui = T.get("ui", {})
    img = esc(coupon.get("image_url", ""))
    title = esc(coupon.get("title", ""))
    alt = esc(alt_text(coupon.get("title", "")))
    price = format_price(coupon.get("price", ""), T)
    original = format_price(coupon.get("original_price", ""), T)
    disc = coupon.get("discount_pct") or 0
    href = esc(coupon.get("affiliate_url", f"{site_url}/{lang}/coupons/"))
    disc_html = f'<span class="coupon-badge">-{int(disc)}% {ui.get("card_off", "OFF")}</span>' if disc else ""
    img_html = (
        f'<a href="{href}" rel="nofollow sponsored noopener" class="product-card__img">'
        f'<img src="{img}" alt="{alt}" width="300" height="300" loading="lazy" decoding="async"></a>'
    ) if img else ""
    return (
        '<article class="product-card">'
        f'{img_html}'
        '<div class="product-card__body">'
        f'{disc_html}'
        f'<h3 class="product-card__title"><a href="{href}" rel="nofollow sponsored noopener">{title}</a></h3>'
        f'<div class="product-card__price"><span class="price">{price}</span>'
        f'<span class="price--old">{original}</span></div>'
        f'<a class="btn-cta product-card__cta" href="{href}" rel="nofollow sponsored noopener">{ui.get("card_get_deal", "Get deal &#8594;")}</a>'
        "</div></article>"
    )


def article_card_html(article: dict, site_url: str, lang: str, T: dict) -> str:
    slug = esc(article.get("slug", ""))
    title = esc(article.get("title", ""))
    date = esc(article.get("date", ""))
    meta_desc = esc(article.get("meta_desc", article.get("meta_description", "")))
    category = article.get("category", "")
    cat_name = category_name(T, category) if category else ""
    img = esc(article.get("image_url", ""))
    alt = esc(alt_text(article.get("title", "")))
    href = f"{site_url}/{lang}/blog/{slug}/"
    img_html = (
        f'<a href="{href}"><img class="blog-card__img" src="{img}" alt="{alt}" '
        f'width="400" height="220" loading="lazy" decoding="async"></a>'
    ) if img else ""
    cat_html = f'<p class="blog-card__cat">{cat_name}</p>' if cat_name else ""
    return (
        f'<article class="blog-card">'
        f'{img_html}'
        f'<div class="blog-card__body">'
        f'{cat_html}'
        f'<h3 class="blog-card__title"><a href="{href}">{title}</a></h3>'
        f'<p class="blog-card__excerpt">{meta_desc}</p>'
        f'<p class="product-card__meta"><time datetime="{date}">{date}</time></p>'
        f'</div>'
        f'</article>'
    )


def related_products_section_html(
    category_slug: str, products_by_cat: dict, site_url: str, lang: str, T: dict,
    limit: int = 4, max_price: float = None, topic_kws=None
) -> str:
    if not category_slug or category_slug not in products_by_cat:
        return ""
    all_products = products_by_cat[category_slug].get("products", [])
    candidates = all_products
    if topic_kws:
        _topic_pat = re.compile('|'.join(re.escape(k) for k in topic_kws), re.IGNORECASE)
        _topic_matches = [p for p in all_products if _topic_pat.search(p.get("title", ""))]
        if len(_topic_matches) < 2:
            return ""
        candidates = _topic_matches
    if max_price is not None:
        _price_filtered = [p for p in candidates if _price_val(p) <= max_price]
        candidates = _price_filtered if len(_price_filtered) >= 2 else candidates
    products = candidates[:limit]
    if not products:
        return ""
    cat_name = category_name(T, category_slug)
    cat = T.get("category", {})
    title = cat.get("related_title", "Top {category_name} deals right now").format(category_name=cat_name)
    browse = cat.get("related_browse", "Browse all {category_name} deals &#8594;").format(category_name=cat_name)
    cards = "".join(product_card_html(p, category_slug, site_url, lang, T) for p in products)
    return (
        f'<section class="related-products">'
        f'<h2 class="related-products__title">{title}</h2>'
        f'<div class="product-grid">{cards}</div>'
        f'<p class="related-products__cta">'
        f'<a class="btn-cta" href="{site_url}/{lang}/{category_slug}/">'
        f'{browse}</a></p>'
        f'</section>'
    )


def article_product_card_html(product: dict, T: dict) -> str:
    """Product card for the in-article 'Recommended products' section. Unlike
    product_card_html it links straight to the affiliate URL (no internal
    product page exists for these), mirroring deal_card_html's affiliate link
    pattern with rel="nofollow sponsored noopener" and target _blank."""
    href = esc(product.get("affiliate_url", ""))
    img = esc(product.get("image_url", ""))
    title = esc(product.get("title", ""))
    alt = esc(alt_text(product.get("title", "")))
    price = format_price(product.get("price", ""), T)
    original = format_price(product.get("original_price", ""), T)
    disc = product.get("discount_pct") or 0
    rating = product.get("rating") or 0
    reviews = product.get("reviews_count") or 0
    ui = T.get("ui", {})
    rel = ' rel="nofollow sponsored noopener" target="_blank"'
    disc_html = f'<span class="price--off">-{int(disc)}%</span>' if disc else ""
    return (
        '<article class="product-card">'
        f'<a href="{href}"{rel} class="product-card__img">'
        f'<img src="{img}" alt="{alt}" width="300" height="300" loading="lazy" decoding="async"></a>'
        '<div class="product-card__body">'
        f'<h3 class="product-card__title"><a href="{href}"{rel}>{title}</a></h3>'
        f'<div class="product-card__price"><span class="price">{price}</span>'
        f'<span class="price--old">{original}</span>{disc_html}</div>'
        f'<p class="product-card__meta">{ui.get("card_rating", "Rating")}: {rating}/5 &middot; {reviews} {ui.get("card_reviews", "reviews")}</p>'
        f'<a class="btn-cta product-card__cta" href="{href}"{rel}>{ui.get("card_see_deal", "See deal &#8594;")}</a>'
        "</div></article>"
    )


def article_products_section_html(products: list, T: dict, limit: int = 4) -> str:
    """In-article recommended-products section: cards link directly to the
    affiliate URL (the products have no internal page). Title from the
    blog_post.recommended_products i18n label, not a raw slug."""
    items = [p for p in products if p.get("affiliate_url")][:limit]
    if not items:
        return ""
    title = T.get("blog_post", {}).get("recommended_products", "Recommended products")
    cards = "".join(article_product_card_html(p, T) for p in items)
    return (
        '<section class="related-products">'
        f'<h2 class="related-products__title">{title}</h2>'
        f'<div class="product-grid">{cards}</div>'
        '</section>'
    )


def _extract_faq_schema(content_html: str) -> str:
    pairs = re.findall(
        r'<summary[^>]*>(.*?)</summary>\s*<(?:p|div)[^>]*>(.*?)</(?:p|div)>',
        content_html, re.DOTALL | re.IGNORECASE
    )
    if not pairs:
        return ''
    items = [
        {
            "@type": "Question",
            "name": re.sub(r'<[^>]+>', '', q).strip(),
            "acceptedAnswer": {"@type": "Answer", "text": re.sub(r'<[^>]+>', '', a).strip()}
        }
        for q, a in pairs
    ]
    schema = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": items}
    return f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>'


def _build_faq_schema(faqs: list) -> str:
    items = [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
        for q, a in faqs
    ]
    schema = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": items}
    return f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>'


def hreflang_alternates(site_url: str, path: str, languages: list, default_lang: str) -> str:
    lines = []
    for lng in languages:
        lines.append(
            f'<link rel="alternate" hreflang="{lng}" href="{site_url}/{lng}/{path}">'
        )
    lines.append(
        f'<link rel="alternate" hreflang="x-default" href="{site_url}/{default_lang}/{path}">'
    )
    return "\n  ".join(lines)


def lang_label(lng: str) -> str:
    """Flag emoji + short uppercase code for a language, used in the switcher.
    Falls back to the i18n _meta locale_name when no flag is mapped."""
    flag = LANG_FLAGS.get(lng)
    if flag:
        return f"{flag} {lng.upper()}"
    return load_i18n(lng).get("_meta", {}).get("locale_name", lng.upper())


def lang_switcher_html(site_url: str, current_lang: str, path: str, languages: list) -> str:
    """Nav language switcher pointing at the same page (identical slug) in each
    active language. The current language is rendered as a non-link span.
    `path` is the page path after `/{lang}/`, e.g. "", "electronics/",
    "blog/some-slug/"."""
    if len(languages) < 2:
        return ""
    items = []
    for lng in languages:
        label = lang_label(lng)
        if lng == current_lang:
            items.append(
                f'<span class="lang-switcher__item lang-switcher__item--current" '
                f'aria-current="true">{label}</span>'
            )
        else:
            items.append(
                f'<a class="lang-switcher__item" href="{site_url}/{lng}/{path}" '
                f'hreflang="{lng}">{label}</a>'
            )
    return (
        '<div class="lang-switcher" role="group" aria-label="Language">'
        + "".join(items)
        + "</div>"
    )


def base_context(site_url: str, lang: str, T: dict, languages: list, default_lang: str) -> dict:
    ctx = {
        "site_title": SITE_TITLE,
        "site_description": SITE_DESCRIPTION,
        "site_url": site_url,
        "lang": lang,
        "year": str(datetime.now(timezone.utc).year),
        "lang_switcher_html": "",
    }
    for key, value in T.get("ui", {}).items():
        ctx[f"t_{key}"] = value
    return ctx


def build_home(site_url: str, lang: str, T: dict, out_dir: Path,
               languages: list, default_lang: str, flash_deals: list, articles: list) -> None:
    tpl = load_template("home.html")
    flash_html = "".join(deal_card_html(d, site_url, lang, T) for d in flash_deals[:8])
    blog_html = "".join(article_card_html(a, site_url, lang, T) for a in articles[:6])
    ctx = base_context(site_url, lang, T, languages, default_lang)
    h = T.get("home", {})
    for key, value in h.items():
        ctx[f"h_{key}"] = value
    ctx["title"] = h.get("title", "")
    ctx["site_description"] = h.get("meta_desc", SITE_DESCRIPTION)
    ctx.update({
        "canonical_url": f"{site_url}/{lang}/",
        "hreflang_alternates": hreflang_alternates(site_url, "", languages, default_lang),
        "lang_switcher_html": lang_switcher_html(site_url, lang, "", languages),
        "flash_preview_html": flash_html or f'<p>{T["ui"].get("no_flash_deals", "")}</p>',
        "blog_preview_html": blog_html or f'<p>{T["ui"].get("no_articles_home", "")}</p>',
    })
    write_file(out_dir / "index.html", render(tpl, ctx))


def build_categories(site_url: str, lang: str, T: dict, out_dir: Path,
                     languages: list, default_lang: str, products_by_cat: dict) -> None:
    tpl = load_template("category.html")
    seo_all = T.get("category_seo", {})
    cat_t = T.get("category", {})
    for slug, data in products_by_cat.items():
        products = data.get("products", [])
        ctx = base_context(site_url, lang, T, languages, default_lang)
        cat_name = category_name(T, slug)
        seo = seo_all.get(slug, {})
        faqs = seo.get("faqs", [])
        guide_html = (
            f'<h2>{seo["guide_h2"]}</h2>{seo["guide_body"]}'
            f'<h2>{seo["faq_h2"]}</h2>'
            f'<div class="faq">'
            + "".join(
                f'<details><summary>{q}</summary><p>{a}</p></details>'
                for q, a in faqs
            )
            + "</div>"
        ) if seo else ""
        ctx.update({
            "canonical_url": f"{site_url}/{lang}/{slug}/",
            "hreflang_alternates": hreflang_alternates(site_url, f"{slug}/", languages, default_lang),
            "lang_switcher_html": lang_switcher_html(site_url, lang, f"{slug}/", languages),
            "title": cat_t.get("title", "{category_name} Deals on AliExpress | {site_title}").format(
                category_name=cat_name, site_title=SITE_TITLE),
            "meta_description": cat_t.get("meta_desc", "").format(category_name=cat_name),
            "og_title": cat_t.get("og_title", "").format(category_name=cat_name),
            "og_desc": cat_t.get("og_desc", "").format(category_name=cat_name),
            "category_name": cat_name,
            "category_slug": slug,
            "category_h1": seo.get("h1", f"{cat_name} Deals on AliExpress"),
            "category_intro_html": seo.get("intro", ""),
            "category_guide_html": guide_html,
            "faq_schema_html": _build_faq_schema(faqs) if faqs else "",
            "products_html": "".join(product_card_html(p, slug, site_url, lang, T) for p in products),
            "products_count": str(len(products)),
            "lede_updated": cat_t.get("lede_updated", "Updated"),
            "lede_products": cat_t.get("lede_products", "products"),
            "updated_at": esc(data.get("updated_at", "")),
        })
        write_file(out_dir / slug / "index.html", render(tpl, ctx))


def build_products(site_url: str, lang: str, T: dict, out_dir: Path,
                   languages: list, default_lang: str, products_by_cat: dict) -> None:
    tpl = load_template("product.html")
    p_t = T.get("product", {})
    sym = currency_symbol(T)
    ccode = currency_code(T)
    ship_country = T.get("_meta", {}).get("ship_country", "UK")
    flat = []
    for slug, data in products_by_cat.items():
        for p in data.get("products", []):
            flat.append((slug, p))
    for cat_slug, product in flat:
        related = [
            p for s, p in flat
            if s == cat_slug and p.get("product_id") != product.get("product_id")
        ][:4]
        related_html = "".join(product_card_html(p, cat_slug, site_url, lang, T) for p in related)
        price_history = product.get("price_history") or [
            {"date": product.get("fetched_at", ""), "price": product.get("price", "")}
        ]
        price_history_json = (
            json.dumps(price_history, ensure_ascii=False)
            .replace('"', "&quot;")
        )
        product_slug = product.get("slug", "")
        og_image = product.get("image_url") or f"{site_url}{DEFAULT_OG_IMAGE_PATH}"
        cat_name = category_name(T, cat_slug)
        ctx = base_context(site_url, lang, T, languages, default_lang)
        for key, value in p_t.items():
            ctx[f"p_{key}"] = value
        ctx["p_ships_to"] = p_t.get("ships_to", "Ships to {ship_country}").format(ship_country=ship_country)
        ctx["p_form_target_label"] = p_t.get("form_target_label", "Target price ({currency})").format(currency=ccode)
        ctx["p_form_consent"] = p_t.get("form_consent", "").format(site_url=site_url, lang=lang)
        ctx.update({
            "canonical_url": f"{site_url}/{lang}/{cat_slug}/{product_slug}/",
            "hreflang_alternates": hreflang_alternates(
                site_url, f"{cat_slug}/{product_slug}/", languages, default_lang),
            "lang_switcher_html": lang_switcher_html(
                site_url, lang, f"{cat_slug}/{product_slug}/", languages),
            "currency_symbol": sym,
            "currency_code": ccode,
            "title": esc(product.get("title", "")),
            "title_short": esc(short_title(product.get("title", ""), 43)),
            "meta_description": esc(meta_desc_from_product(product, T)),
            "category_slug": cat_slug,
            "category_name": cat_name,
            "category_particle_effect": CATEGORY_PARTICLES.get(cat_slug, "electric"),
            "slug": esc(product_slug),
            "product_id": esc(product.get("product_id", "")),
            "image_url": esc(product.get("image_url", "")),
            "image_alt": esc(alt_text(product.get("title", ""))),
            "og_image": esc(og_image),
            "price": esc(product.get("price", "")),
            "original_price": esc(product.get("original_price", "")),
            "price_display": format_price(product.get("price", ""), T),
            "original_price_display": format_price(product.get("original_price", ""), T),
            "discount_pct": esc(product.get("discount_pct", 0)),
            "rating": esc(product.get("rating", 0)),
            "reviews_count": esc(product.get("reviews_count", 0)),
            "orders_count": esc(product.get("orders_count", product.get("reviews_count", 0))),
            "shipping_days": DEFAULT_SHIPPING_DAYS,
            "affiliate_url": esc(product.get("affiliate_url", "")),
            "price_history_json": price_history_json,
            "related_products_html": related_html,
        })
        write_file(
            out_dir / cat_slug / product_slug / "index.html",
            render(tpl, ctx),
        )


def build_blog_index(site_url: str, lang: str, T: dict, out_dir: Path,
                     languages: list, default_lang: str, articles: list) -> None:
    tpl = load_template("blog-index.html")
    bi = T.get("blog_index", {})
    months = T.get("months", {})
    ctx = base_context(site_url, lang, T, languages, default_lang)
    ctx["canonical_url"] = f"{site_url}/{lang}/blog/"
    ctx["hreflang_alternates"] = hreflang_alternates(site_url, "blog/", languages, default_lang)
    ctx["lang_switcher_html"] = lang_switcher_html(site_url, lang, "blog/", languages)
    ctx["title"] = bi.get("title", "").format(site_title=SITE_TITLE)
    ctx["meta_description"] = bi.get("meta_desc", "")
    ctx["blog_h1"] = bi.get("h1", "")
    ctx["blog_lede"] = bi.get("lede", "")

    RECENT_COUNT = 7
    recent_articles = articles[:RECENT_COUNT]
    older_articles = articles[RECENT_COUNT:]

    if older_articles:
        archive: dict = {}
        for a in older_articles:
            month_key = a.get("date", "")[:7]
            if month_key not in archive:
                archive[month_key] = []
            archive[month_key].append(a)

        archive_items_html = ""
        for month_key in sorted(archive.keys(), reverse=True):
            arts = archive[month_key]
            month_label = month_key
            parts = month_key.split("-")
            if len(parts) == 2 and parts[1] in months:
                month_label = f"{months[parts[1]]} {parts[0]}"
            count = len(arts)
            items = ""
            for a in arts:
                slug = esc(a.get("slug", ""))
                title = esc(a.get("title", ""))
                date = esc(a.get("date", ""))
                cat = a.get("category", "")
                cat_name = category_name(T, cat) if cat else ""
                href = f"{site_url}/{lang}/blog/{slug}/"
                items += f'<div class="archive-item"><a href="{href}">{title}</a><span class="archive-item__meta">{date} · {cat_name}</span></div>'
            article_word = bi.get("article_plural", "articles") if count != 1 else bi.get("article_singular", "article")
            archive_items_html += f'<div class="archive-month"><h3 class="archive-month__heading">{month_label} · {count} {article_word}</h3><div class="archive-list">{items}</div></div>'

        archive_section_html = f'<section class="archive-section"><h2 class="archive-section__title">{bi.get("archive_title", "Archive")}</h2>{archive_items_html}</section>'
    else:
        archive_section_html = ""

    ctx["articles_html"] = (
        "".join(article_card_html(a, site_url, lang, T) for a in recent_articles)
        or f'<p>{T["ui"].get("no_articles", "")}</p>'
    )
    ctx["archive_section_html"] = archive_section_html
    write_file(out_dir / "blog" / "index.html", render(tpl, ctx))


def related_articles_section_html(current: dict, articles: list, site_url: str, lang: str, T: dict, limit: int = 3) -> str:
    current_slug = current.get("slug", "")
    current_cat = current.get("category", "")
    pool = [a for a in articles if a.get("slug", "") != current_slug]
    same_cat = [a for a in pool if a.get("category", "") == current_cat and current_cat]
    picked = list(same_cat[:limit])
    if len(picked) < limit:
        picked_slugs = {a.get("slug", "") for a in picked}
        for a in pool:
            if a.get("slug", "") in picked_slugs:
                continue
            picked.append(a)
            picked_slugs.add(a.get("slug", ""))
            if len(picked) >= limit:
                break
    if not picked:
        return ""
    cards = "".join(article_card_html(a, site_url, lang, T) for a in picked)
    title = T.get("blog_post", {}).get("related_articles", "Related articles")
    return (
        '<section class="related-articles">'
        f'<h2 class="related-articles__title">{title}</h2>'
        f'<div class="grid grid--posts">{cards}</div>'
        '</section>'
    )


def _redirect_stub_html(site_url: str, lang: str, target_slug: str, site_title: str) -> str:
    """Minimal noindex stub for a consolidated (weak) article: instant meta
    refresh + canonical to the strong article, with a manual link fallback."""
    target = f"{site_url}/{lang}/blog/{esc(target_slug)}/"
    return (
        "<!doctype html>\n"
        f'<html lang="{lang}">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="robots" content="noindex, follow">\n'
        f'<meta http-equiv="refresh" content="0;url={target}">\n'
        f'<link rel="canonical" href="{target}">\n'
        f"<title>{esc(site_title)}</title>\n"
        "</head>\n"
        "<body>\n"
        f'<script>window.location.replace("{target}");</script>\n'
        f'<p><a href="{target}">{target}</a></p>\n'
        "</body>\n"
        "</html>\n"
    )


def build_blog_posts(site_url: str, lang: str, T: dict, out_dir: Path,
                     languages: list, default_lang: str, articles: list, products_by_cat: dict) -> None:
    tpl = load_template("blog-post.html")
    bp = T.get("blog_post", {})

    _article_products: dict = {}
    _article_dir = DATA_DIR / "products" / lang / "_article"
    if not _article_dir.exists():
        _article_dir = DATA_DIR / "products" / "en" / "_article"
    if _article_dir.exists():
        for _f in _article_dir.glob("*.json"):
            _d = load_json(_f, default={"products": []})
            if _d:
                _article_products[_f.stem] = _d

    for article in articles:
        slug = article.get("slug", "")
        redirect_to = article.get("redirect_to")
        if redirect_to:
            # F5 consolidation: render a noindex stub that redirects to the
            # canonical (strong) article. Kept out of the blog index, sitemap
            # and related-articles pool (filtered by the callers).
            write_file(
                out_dir / "blog" / slug / "index.html",
                _redirect_stub_html(site_url, lang, redirect_to, SITE_TITLE),
            )
            continue
        category_slug = article.get("category", "")
        title = article.get("title", "")
        primary_kw = article.get("primary_keyword", "")
        max_price = _extract_price_ceiling(title) or _extract_price_ceiling(primary_kw)
        combined = f"{title} {primary_kw}"
        topic_kws = None
        for _detect_pat, _filter_kws in _SPECIFIC_PRODUCT_TERMS:
            if _detect_pat.search(combined):
                topic_kws = _filter_kws
                break
        related_section = ""
        if slug in _article_products and _article_products[slug].get("products"):
            related_section = article_products_section_html(
                _article_products[slug]["products"], T, limit=4
            )
        if not related_section:
            related_section = related_products_section_html(
                category_slug, products_by_cat, site_url, lang, T, limit=4,
                max_price=max_price, topic_kws=topic_kws
            )
        og_image = article.get("image_url") or f"{site_url}{DEFAULT_OG_IMAGE_PATH}"
        content_html = article.get("content_html", article.get("content", ""))
        content_html = re.sub(r'<h1(\s[^>]*)?>', r'<h2\1>', content_html, flags=re.IGNORECASE)
        content_html = re.sub(r'</h1>', '</h2>', content_html, flags=re.IGNORECASE)
        faq_schema_html = _extract_faq_schema(content_html)
        related_articles_html = related_articles_section_html(
            article, visible_articles(articles), site_url, lang, T, limit=3)
        ctx = base_context(site_url, lang, T, languages, default_lang)
        ctx["bp_min_read"] = bp.get("min_read", "min read")
        ctx["bp_ai_note"] = bp.get("ai_note", "AI-assisted content")
        ctx["bp_ai_disclosure"] = bp.get("ai_disclosure", "")
        ctx["bp_affiliate_disclosure"] = bp.get("affiliate_disclosure", "")
        ctx.update({
            "canonical_url": f"{site_url}/{lang}/blog/{slug}/",
            "hreflang_alternates": hreflang_alternates(site_url, f"blog/{slug}/", languages, default_lang),
            "lang_switcher_html": lang_switcher_html(site_url, lang, f"blog/{slug}/", languages),
            "title": esc(article.get("title", "")),
            "title_short": esc(short_title(article.get("title", ""), 60)),
            "slug": esc(slug),
            "date": esc(article.get("date", "")),
            "meta_description": esc(article.get("meta_desc", article.get("meta_description", ""))),
            "content_html": content_html,
            "reading_time_min": esc(article.get("reading_time_min", 5)),
            "og_image": og_image,
            "category_slug": esc(category_slug),
            "category_name": esc(category_name(T, category_slug)),
            "related_products_section": related_section,
            "related_articles_html": related_articles_html,
            "faq_schema_html": faq_schema_html,
        })
        write_file(
            out_dir / "blog" / slug / "index.html",
            render(tpl, ctx),
        )


def build_flash_sale(site_url: str, lang: str, T: dict, out_dir: Path,
                     languages: list, default_lang: str, flash_deals: list, updated_at: str) -> None:
    tpl = load_template("flash-sale.html")
    fl = T.get("flash", {})
    ctx = base_context(site_url, lang, T, languages, default_lang)
    faqs = fl.get("faqs", [])
    flash_guide_html = (
        f'<h2>{fl.get("guide_h2_1", "")}</h2>'
        f'<p>{fl.get("guide_p1", "")}</p>'
        f'<p>{fl.get("guide_p2", "")}</p>'
        f'<h2>{fl.get("guide_h2_2", "")}</h2>'
        '<div class="faq">'
        + "".join(
            f'<details><summary>{q}</summary><p>{a}</p></details>'
            for q, a in faqs
        )
        + "</div>"
    )
    ctx["title"] = fl.get("title", "").format(site_title=SITE_TITLE)
    ctx["meta_description"] = fl.get("meta_desc", "")
    ctx["og_title"] = fl.get("og_title", "")
    ctx["og_desc"] = fl.get("og_desc", "")
    ctx["flash_h1"] = fl.get("h1", "Flash Sale")
    ctx["lede_updated"] = fl.get("lede_updated", "Updated")
    ctx["lede_deals"] = fl.get("lede_deals", "deals live now")
    ctx.update({
        "canonical_url": f"{site_url}/{lang}/flash-sale/",
        "hreflang_alternates": hreflang_alternates(site_url, "flash-sale/", languages, default_lang),
        "lang_switcher_html": lang_switcher_html(site_url, lang, "flash-sale/", languages),
        "deals_html": (
            "".join(deal_card_html(d, site_url, lang, T) for d in flash_deals)
            or f'<p>{T["ui"].get("no_flash_deals", "")}</p>'
        ),
        "deals_count": str(len(flash_deals)),
        "updated_at": esc(updated_at),
        "flash_intro_html": fl.get("intro_html", ""),
        "flash_guide_html": flash_guide_html,
        "faq_schema_html": _build_faq_schema(faqs) if faqs else "",
    })
    write_file(out_dir / "flash-sale" / "index.html", render(tpl, ctx))


def build_coupons(site_url: str, lang: str, T: dict, out_dir: Path,
                  languages: list, default_lang: str, coupons: list, updated_at: str) -> None:
    tpl = load_template("coupon-page.html")
    cp = T.get("coupons", {})
    ctx = base_context(site_url, lang, T, languages, default_lang)
    faqs = cp.get("faqs", [])
    coupons_guide_html = (
        f'<h2>{cp.get("guide_h2_1", "")}</h2>'
        f'<p>{cp.get("guide_p1", "")}</p>'
        f'<p>{cp.get("guide_p2", "")}</p>'
        f'<h2>{cp.get("guide_h2_2", "")}</h2>'
        '<div class="faq">'
        + "".join(
            f'<details><summary>{q}</summary><p>{a}</p></details>'
            for q, a in faqs
        )
        + "</div>"
    )
    ctx["title"] = cp.get("title", "").format(site_title=SITE_TITLE)
    ctx["meta_description"] = cp.get("meta_desc", "")
    ctx["og_title"] = cp.get("og_title", "")
    ctx["og_desc"] = cp.get("og_desc", "")
    ctx["coupons_h1"] = cp.get("h1", "")
    ctx["coupons_lede"] = cp.get("lede", "")
    ctx["lede_updated"] = cp.get("lede_updated", "Updated")
    ctx["lede_deals"] = cp.get("lede_deals", "active deals")
    ctx.update({
        "canonical_url": f"{site_url}/{lang}/coupons/",
        "hreflang_alternates": hreflang_alternates(site_url, "coupons/", languages, default_lang),
        "lang_switcher_html": lang_switcher_html(site_url, lang, "coupons/", languages),
        "coupons_html": (
            "".join(coupon_card_html(c, site_url, lang, T) for c in coupons)
            or f'<p>{T["ui"].get("no_coupons", "")}</p>'
        ),
        "coupons_count": str(len(coupons)),
        "updated_at": esc(updated_at),
        "coupons_intro_html": cp.get("intro_html", ""),
        "coupons_guide_html": coupons_guide_html,
        "faq_schema_html": _build_faq_schema(faqs) if faqs else "",
    })
    write_file(out_dir / "coupons" / "index.html", render(tpl, ctx))


def build_static_pages(site_url: str, lang: str, T: dict, out_dir: Path,
                       languages: list, default_lang: str) -> None:
    for slug in STATIC_PAGES:
        tpl_path = TEMPLATES_DIR / lang / f"{slug}.html"
        if not tpl_path.exists():
            tpl_path = TEMPLATES_DIR / f"{slug}.html"
        if not tpl_path.exists():
            print(f"  [warn] template {slug}.html missing, skip")
            continue
        tpl = tpl_path.read_text(encoding="utf-8")
        ctx = base_context(site_url, lang, T, languages, default_lang)
        ctx.update({
            "canonical_url": f"{site_url}/{lang}/{slug}/",
            "hreflang_alternates": hreflang_alternates(site_url, f"{slug}/", languages, default_lang),
            "lang_switcher_html": lang_switcher_html(site_url, lang, f"{slug}/", languages),
        })
        page_out = out_dir / slug
        page_out.mkdir(parents=True, exist_ok=True)
        (page_out / "index.html").write_text(render(tpl, ctx), encoding="utf-8")
        print(f"  -> {lang}/{slug}/index.html")


def _sitemap_priority(url: str, site_url: str) -> str:
    path = url[len(site_url):] if url.startswith(site_url) else url
    for slug in LOW_PRIORITY_PAGES:
        if path.rstrip("/").endswith(f"/{slug}"):
            return "0.1"
    return "0.7"


def build_sitemap(site_url: str, languages: list, products_by_cat: dict, articles: list) -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    urls = []
    for lang in languages:
        urls.extend([
            f"{site_url}/{lang}/",
            f"{site_url}/{lang}/flash-sale/",
            f"{site_url}/{lang}/coupons/",
            f"{site_url}/{lang}/blog/",
        ])
        for slug in STATIC_PAGES:
            urls.append(f"{site_url}/{lang}/{slug}/")
        for slug in products_by_cat:
            urls.append(f"{site_url}/{lang}/{slug}/")
        for a in articles:
            urls.append(f"{site_url}/{lang}/blog/{a.get('slug', '')}/")
    seen = set()
    urls = [u for u in urls if not (u in seen or seen.add(u))]
    body = "\n".join(
        f"  <url><loc>{u}</loc><lastmod>{today}</lastmod>"
        f"<priority>{_sitemap_priority(u, site_url)}</priority></url>"
        for u in urls
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n</urlset>\n"
    )
    write_file(BASE_DIR / "sitemap.xml", xml)


def build_robots(site_url: str) -> None:
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {site_url}/sitemap.xml\n"
    )
    write_file(BASE_DIR / "robots.txt", content)


def build_indexnow_key(indexnow_key: str) -> None:
    """Write the IndexNow key verification file to the output root so it is
    served at https://<host>/<key>.txt (content = the key). Required by the
    IndexNow protocol to prove ownership before accepting URL submissions."""
    if not indexnow_key:
        return
    write_file(BASE_DIR / f"{indexnow_key}.txt", indexnow_key)


def build_404(site_url: str, default_lang: str, T: dict, languages: list) -> None:
    nf = T.get("notfound", {})
    ui = T.get("ui", {})
    tpl = load_template("404.html")
    # Per-language 404 strings for the client-side switcher: the page is a
    # single /404.html served by the host for every path, so a small JS reads
    # the path prefix (/it/, /es/, ...) and swaps text + lang + internal link
    # prefix. The default language is the no-JS fallback already in the HTML.
    nf_i18n = {}
    for lng in languages:
        if lng == default_lang:
            continue
        lnf = load_i18n(lng).get("notfound", {})
        nf_i18n[lng] = {
            "title": lnf.get("title", nf.get("title", "")),
            "h1": lnf.get("h1", nf.get("h1", "")),
            "body": lnf.get("body", nf.get("body", "")),
            "back_home": lnf.get("back_home", nf.get("back_home", "")),
            "browse_categories": lnf.get("browse_categories", nf.get("browse_categories", "")),
        }
    ctx = {
        "site_title": SITE_TITLE,
        "site_url": site_url,
        "lang": default_lang,
        "default_lang": default_lang,
        "year": str(datetime.now(timezone.utc).year),
        "lang_switcher_html": lang_switcher_html(site_url, default_lang, "", languages),
        "nf_title": nf.get("title", "Page not found"),
        "nf_meta_desc": nf.get("meta_desc", ""),
        "nf_h1": nf.get("h1", "Page not found"),
        "nf_body": nf.get("body", ""),
        "nf_back_home": nf.get("back_home", "Back to homepage &#8594;"),
        "nf_browse_categories": nf.get("browse_categories", "Browse our categories"),
        "nf_i18n_json": json.dumps(nf_i18n, ensure_ascii=False),
    }
    for key, value in ui.items():
        ctx[f"t_{key}"] = value
    write_file(BASE_DIR / "404.html", render(tpl, ctx))


def build_root_index(site_url: str, languages: list, default_lang: str) -> None:
    """Root index.html: instant redirect to the default language plus a
    visible <noscript> list of all active languages (graceful fallback)."""
    langs = languages or ["en"]
    redirect_lang = default_lang if default_lang in langs else langs[0]
    links = []
    for lng in langs:
        meta = load_i18n(lng).get("_meta", {})
        label = meta.get("locale_name", lng.upper())
        links.append(f'<li><a href="/{lng}/">{html.escape(label)}</a></li>')
    links_html = "\n      ".join(links)
    content = (
        "<!DOCTYPE html>\n"
        f'<html lang="{redirect_lang}">\n'
        "<head>\n"
        '<meta charset="UTF-8">\n'
        f'<meta http-equiv="refresh" content="0;url=/{redirect_lang}/">\n'
        f'<link rel="canonical" href="{site_url}/{redirect_lang}/">\n'
        "<title>AliGlobalShop</title>\n"
        "</head>\n"
        "<body>\n"
        f'<script>window.location.replace("/{redirect_lang}/");</script>\n'
        "<noscript>\n"
        "    <p>AliGlobalShop</p>\n"
        "    <ul>\n"
        f"      {links_html}\n"
        "    </ul>\n"
        "</noscript>\n"
        "</body>\n"
        "</html>\n"
    )
    write_file(BASE_DIR / "index.html", content)


def load_products(lang: str) -> dict:
    out = {}
    products_dir = DATA_DIR / "products" / lang
    if not products_dir.exists() or not any(products_dir.glob("*.json")):
        products_dir = DATA_DIR / "products" / "en"
    if not products_dir.exists():
        return out
    for f in products_dir.glob("*.json"):
        data = load_json(f, default={"products": []})
        out[f.stem] = data
    return out


def load_articles(lang: str) -> list:
    blog_dir = DATA_DIR / "blog" / lang
    if not blog_dir.exists() or not any(blog_dir.glob("*.json")):
        blog_dir = DATA_DIR / "blog" / "en"
    if not blog_dir.exists():
        return []
    items = []
    for f in sorted(blog_dir.glob("*.json"), reverse=True):
        data = load_json(f)
        if data:
            items.append(data)
    return items


def visible_articles(articles: list) -> list:
    """Articles that should be listed/indexed: excludes F5 consolidation stubs
    (those with a redirect_to). Stub pages are still generated by
    build_blog_posts, just kept out of the index, sitemap and related pool."""
    return [a for a in articles if not a.get("redirect_to")]


def load_flash_deals(lang: str) -> tuple:
    path = DATA_DIR / "flash-sale" / f"{lang}.json"
    if not path.exists():
        path = DATA_DIR / "flash-sale" / "en.json"
    data = load_json(path, default={})
    deals = data.get("deals", data.get("products", []))
    return deals, data.get("updated_at", "")


def load_coupons(lang: str) -> tuple:
    path = DATA_DIR / "coupons" / f"{lang}.json"
    if not path.exists():
        path = DATA_DIR / "coupons" / "en.json"
    data = load_json(path, default={})
    coupons = data.get("coupons", data.get("products", []))
    return coupons, data.get("updated_at", "")


def clean_output(out_dir: Path) -> None:
    if out_dir.exists():
        for child in out_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()


def build_language(site_url: str, lang: str, languages: list, default_lang: str) -> None:
    T = load_i18n(lang)
    out_dir = BASE_DIR / lang
    out_dir.mkdir(parents=True, exist_ok=True)
    clean_output(out_dir)

    products_by_cat = load_products(lang)
    articles = load_articles(lang)
    listed = visible_articles(articles)
    flash_deals, flash_updated = load_flash_deals(lang)
    coupons, coupons_updated = load_coupons(lang)

    print(f"[build:{lang}] categories={len(products_by_cat)} articles={len(listed)} "
          f"(+{len(articles) - len(listed)} stub) "
          f"flash={len(flash_deals)} coupons={len(coupons)}")

    build_home(site_url, lang, T, out_dir, languages, default_lang, flash_deals, listed)
    build_categories(site_url, lang, T, out_dir, languages, default_lang, products_by_cat)
    build_products(site_url, lang, T, out_dir, languages, default_lang, products_by_cat)
    build_blog_index(site_url, lang, T, out_dir, languages, default_lang, listed)
    build_blog_posts(site_url, lang, T, out_dir, languages, default_lang, articles, products_by_cat)
    build_flash_sale(site_url, lang, T, out_dir, languages, default_lang, flash_deals, flash_updated)
    build_coupons(site_url, lang, T, out_dir, languages, default_lang, coupons, coupons_updated)
    build_static_pages(site_url, lang, T, out_dir, languages, default_lang)


def main() -> None:
    config = load_json(CONFIG_PATH, default={})
    site_url = config.get("site_url", "https://aliglobalshop.net").rstrip("/")
    languages = config.get("languages", ["en"]) or ["en"]
    default_lang = config.get("default_language", "en")
    print(f"[build] site_url={site_url} languages={languages} default={default_lang}")

    sitemap_products = load_products(default_lang)
    sitemap_articles = visible_articles(load_articles(default_lang))

    for lang in languages:
        build_language(site_url, lang, languages, default_lang)

    build_sitemap(site_url, languages, sitemap_products, sitemap_articles)
    build_robots(site_url)
    build_indexnow_key(config.get("indexnow_key", ""))
    build_404(site_url, default_lang, load_i18n(default_lang), languages)
    build_root_index(site_url, languages, default_lang)

    print("[build] done")


if __name__ == "__main__":
    main()
