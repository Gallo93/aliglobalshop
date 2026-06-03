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
    return T.get("category_names", {}).get(slug, slug.replace("-", " ").title())


def currency_symbol(T: dict) -> str:
    return T.get("_meta", {}).get("currency_symbol", "$")


def currency_code(T: dict) -> str:
    return T.get("_meta", {}).get("currency", "USD")


def meta_desc_from_product(product: dict, T: dict) -> str:
    base = product.get("title", "")
    price = product.get("price")
    disc = product.get("discount_pct") or 0
    sym = currency_symbol(T)
    p = T.get("product", {})
    only = p.get("meta_only", "only")
    on_ali = p.get("meta_on_aliexpress", "on AliExpress")
    text = f"{base}: {only} {sym}{price} {on_ali}"
    if disc:
        text += f" (-{disc}%)"
    return short_title(text, 155)


def product_card_html(product: dict, category_slug: str, site_url: str, lang: str, T: dict) -> str:
    href = f"{site_url}/{lang}/{category_slug}/{esc(product.get('slug', ''))}/"
    img = esc(product.get("image_url", ""))
    title = esc(product.get("title", ""))
    alt = esc(alt_text(product.get("title", "")))
    price = esc(product.get("price", ""))
    original = esc(product.get("original_price", ""))
    disc = product.get("discount_pct") or 0
    rating = product.get("rating") or 0
    reviews = product.get("reviews_count") or 0
    sym = currency_symbol(T)
    ui = T.get("ui", {})
    disc_html = f'<span class="price--off">-{int(disc)}%</span>' if disc else ""
    return (
        '<article class="product-card">'
        f'<a href="{href}" class="product-card__img">'
        f'<img src="{img}" alt="{alt}" width="300" height="300" loading="lazy" decoding="async"></a>'
        '<div class="product-card__body">'
        f'<h3 class="product-card__title"><a href="{href}">{title}</a></h3>'
        f'<div class="product-card__price"><span class="price">{sym}{price}</span>'
        f'<span class="price--old">{sym}{original}</span>{disc_html}</div>'
        f'<p class="product-card__meta">{ui.get("card_rating", "Rating")}: {rating}/5 · {reviews} {ui.get("card_reviews", "reviews")}</p>'
        f'<a class="btn-cta product-card__cta" href="{href}">{ui.get("card_see_deal", "See deal &#8594;")}</a>'
        "</div></article>"
    )


def deal_card_html(deal: dict, site_url: str, lang: str, T: dict) -> str:
    category_slug = deal.get("category", "")
    sym = currency_symbol(T)
    ui = T.get("ui", {})
    if category_slug:
        href = f"{site_url}/{lang}/{category_slug}/{esc(deal.get('slug', ''))}/"
        link_rel = ""
    else:
        href = esc(deal.get("affiliate_url", f"{site_url}/{lang}/flash-sale/"))
        link_rel = ' rel="nofollow sponsored"'
    img = esc(deal.get("image_url", ""))
    title = esc(deal.get("title", ""))
    alt = esc(alt_text(deal.get("title", "")))
    price = esc(deal.get("price", ""))
    original = esc(deal.get("original_price", ""))
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
        f'<div class="product-card__price"><span class="price">{sym}{price}</span>'
        f'<span class="price--old">{sym}{original}</span>{disc_html}</div>'
        f'<p class="product-card__meta">{ui.get("card_ends_in", "Ends in")}: {countdown}</p>'
        f'<a class="btn-cta product-card__cta" href="{href}"{link_rel}>{ui.get("card_grab_it", "Grab it &#8594;")}</a>'
        "</div></article>"
    )


def coupon_card_html(coupon: dict, site_url: str, lang: str, T: dict) -> str:
    sym = currency_symbol(T)
    ui = T.get("ui", {})
    img = esc(coupon.get("image_url", ""))
    title = esc(coupon.get("title", ""))
    alt = esc(alt_text(coupon.get("title", "")))
    price = esc(coupon.get("price", ""))
    original = esc(coupon.get("original_price", ""))
    disc = coupon.get("discount_pct") or 0
    href = esc(coupon.get("affiliate_url", f"{site_url}/{lang}/coupons/"))
    disc_html = f'<span class="coupon-badge">-{int(disc)}% {ui.get("card_off", "OFF")}</span>' if disc else ""
    img_html = (
        f'<a href="{href}" rel="nofollow sponsored" class="product-card__img">'
        f'<img src="{img}" alt="{alt}" width="300" height="300" loading="lazy" decoding="async"></a>'
    ) if img else ""
    return (
        '<article class="product-card">'
        f'{img_html}'
        '<div class="product-card__body">'
        f'{disc_html}'
        f'<h3 class="product-card__title"><a href="{href}" rel="nofollow sponsored">{title}</a></h3>'
        f'<div class="product-card__price"><span class="price">{sym}{price}</span>'
        f'<span class="price--old">{sym}{original}</span></div>'
        f'<a class="btn-cta product-card__cta" href="{href}" rel="nofollow sponsored">{ui.get("card_get_deal", "Get deal &#8594;")}</a>'
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


def base_context(site_url: str, lang: str, T: dict, languages: list, default_lang: str) -> dict:
    ctx = {
        "site_title": SITE_TITLE,
        "site_description": SITE_DESCRIPTION,
        "site_url": site_url,
        "lang": lang,
        "year": str(datetime.now(timezone.utc).year),
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
    ctx.update({
        "canonical_url": f"{site_url}/{lang}/",
        "hreflang_alternates": hreflang_alternates(site_url, "", languages, default_lang),
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
            related_section = related_products_section_html(
                slug, _article_products, site_url, lang, T, limit=4, max_price=max_price
            )
        if not related_section:
            related_section = related_products_section_html(
                category_slug, products_by_cat, site_url, lang, T, limit=4,
                max_price=max_price, topic_kws=topic_kws
            )
        og_image = f"{site_url}{DEFAULT_OG_IMAGE_PATH}"
        content_html = article.get("content_html", article.get("content", ""))
        content_html = re.sub(r'<h1(\s[^>]*)?>', r'<h2\1>', content_html, flags=re.IGNORECASE)
        content_html = re.sub(r'</h1>', '</h2>', content_html, flags=re.IGNORECASE)
        faq_schema_html = _extract_faq_schema(content_html)
        related_articles_html = related_articles_section_html(article, articles, site_url, lang, T, limit=3)
        ctx = base_context(site_url, lang, T, languages, default_lang)
        ctx["bp_min_read"] = bp.get("min_read", "min read")
        ctx["bp_ai_note"] = bp.get("ai_note", "AI-assisted content")
        ctx["bp_ai_disclosure"] = bp.get("ai_disclosure", "")
        ctx["bp_affiliate_disclosure"] = bp.get("affiliate_disclosure", "")
        ctx.update({
            "canonical_url": f"{site_url}/{lang}/blog/{slug}/",
            "hreflang_alternates": hreflang_alternates(site_url, f"blog/{slug}/", languages, default_lang),
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


def build_404(site_url: str, default_lang: str, T: dict) -> None:
    nf = T.get("notfound", {})
    ui = T.get("ui", {})
    tpl = load_template("404.html")
    ctx = {
        "site_title": SITE_TITLE,
        "site_url": site_url,
        "lang": default_lang,
        "year": str(datetime.now(timezone.utc).year),
        "nf_title": nf.get("title", "Page not found"),
        "nf_meta_desc": nf.get("meta_desc", ""),
        "nf_h1": nf.get("h1", "Page not found"),
        "nf_body": nf.get("body", ""),
        "nf_back_home": nf.get("back_home", "Back to homepage &#8594;"),
        "nf_browse_categories": nf.get("browse_categories", "Browse our categories"),
    }
    for key, value in ui.items():
        ctx[f"t_{key}"] = value
    write_file(BASE_DIR / "404.html", render(tpl, ctx))


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
    flash_deals, flash_updated = load_flash_deals(lang)
    coupons, coupons_updated = load_coupons(lang)

    print(f"[build:{lang}] categories={len(products_by_cat)} articles={len(articles)} "
          f"flash={len(flash_deals)} coupons={len(coupons)}")

    build_home(site_url, lang, T, out_dir, languages, default_lang, flash_deals, articles)
    build_categories(site_url, lang, T, out_dir, languages, default_lang, products_by_cat)
    build_products(site_url, lang, T, out_dir, languages, default_lang, products_by_cat)
    build_blog_index(site_url, lang, T, out_dir, languages, default_lang, articles)
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
    sitemap_articles = load_articles(default_lang)

    for lang in languages:
        build_language(site_url, lang, languages, default_lang)

    build_sitemap(site_url, languages, sitemap_products, sitemap_articles)
    build_robots(site_url)
    build_404(site_url, default_lang, load_i18n(default_lang))

    print("[build] done")


if __name__ == "__main__":
    main()
