"""
Static site generator for AliGlobalShop EN.

Reads JSON in _data/ + templates in _templates/, writes HTML in en/.
Uses str.replace for {{KEY}} placeholders — no Jinja.
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
OUTPUT_DIR = BASE_DIR / "en"
CONFIG_PATH = DATA_DIR / "config.json"

SITE_TITLE = "AliGlobalShop"
SITE_DESCRIPTION = (
    "Curated AliExpress deals, live flash sales and working coupons — updated every day."
)
DEFAULT_SHIPPING_DAYS = "7-25"
DEFAULT_OG_IMAGE_PATH = "/assets/img/og-default.jpg"

CATEGORY_NAMES = {
    "electronics": "Electronics",
    "smart-home": "Smart Home",
    "sport": "Sport",
    "gadgets": "Gadgets",
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

STATIC_PAGES = [
    ("privacy", "Privacy Policy"),
    ("about", "About AliGlobalShop"),
    ("contact", "Contact Us"),
]

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


def meta_desc_from_product(product: dict) -> str:
    base = product.get("title", "")
    price = product.get("price")
    disc = product.get("discount_pct") or 0
    text = f"{base} — only ${price} on AliExpress"
    if disc:
        text += f" (-{disc}%)"
    return short_title(text, 155)


def product_card_html(product: dict, category_slug: str, site_url: str) -> str:
    href = f"{site_url}/en/{category_slug}/{esc(product.get('slug', ''))}/"
    img = esc(product.get("image_url", ""))
    title = esc(product.get("title", ""))
    price = esc(product.get("price", ""))
    original = esc(product.get("original_price", ""))
    disc = product.get("discount_pct") or 0
    rating = product.get("rating") or 0
    reviews = product.get("reviews_count") or 0
    disc_html = f'<span class="price--off">-{int(disc)}%</span>' if disc else ""
    return (
        '<article class="product-card">'
        f'<a href="{href}" class="product-card__img">'
        f'<img src="{img}" alt="{title}" width="300" height="300" loading="lazy" decoding="async"></a>'
        '<div class="product-card__body">'
        f'<h3 class="product-card__title"><a href="{href}">{title}</a></h3>'
        f'<div class="product-card__price"><span class="price">${price}</span>'
        f'<span class="price--old">${original}</span>{disc_html}</div>'
        f'<p class="product-card__meta">Rating: {rating}/5 · {reviews} reviews</p>'
        f'<a class="btn-cta product-card__cta" href="{href}">See deal →</a>'
        "</div></article>"
    )


def deal_card_html(deal: dict, site_url: str) -> str:
    category_slug = deal.get("category", "")
    if category_slug:
        href = f"{site_url}/en/{category_slug}/{esc(deal.get('slug', ''))}/"
        link_rel = ""
    else:
        href = esc(deal.get("affiliate_url", f"{site_url}/en/flash-sale/"))
        link_rel = ' rel="nofollow sponsored"'
    img = esc(deal.get("image_url", ""))
    title = esc(deal.get("title", ""))
    price = esc(deal.get("price", ""))
    original = esc(deal.get("original_price", ""))
    disc = deal.get("discount_pct") or 0
    expires = esc(deal.get("expires_at", ""))
    disc_html = f'<span class="price--off">-{int(disc)}%</span>' if disc else ""
    countdown = f'<span data-expires="{expires}"></span>' if expires else ""
    return (
        '<article class="product-card">'
        f'<a href="{href}"{link_rel} class="product-card__img">'
        f'<img src="{img}" alt="{title}" width="300" height="300" loading="lazy" decoding="async"></a>'
        '<div class="product-card__body">'
        f'<h3 class="product-card__title"><a href="{href}"{link_rel}>{title}</a></h3>'
        f'<div class="product-card__price"><span class="price">${price}</span>'
        f'<span class="price--old">${original}</span>{disc_html}</div>'
        f'<p class="product-card__meta">Ends in: {countdown}</p>'
        f'<a class="btn-cta product-card__cta" href="{href}"{link_rel}>Grab it →</a>'
        "</div></article>"
    )


def coupon_card_html(coupon: dict, site_url: str) -> str:
    img = esc(coupon.get("image_url", ""))
    title = esc(coupon.get("title", ""))
    price = esc(coupon.get("price", ""))
    original = esc(coupon.get("original_price", ""))
    disc = coupon.get("discount_pct") or 0
    href = esc(coupon.get("affiliate_url", f"{site_url}/en/coupons/"))
    disc_html = f'<span class="coupon-badge">-{int(disc)}% OFF</span>' if disc else ""
    img_html = (
        f'<a href="{href}" rel="nofollow sponsored" class="product-card__img">'
        f'<img src="{img}" alt="{title}" width="300" height="300" loading="lazy" decoding="async"></a>'
    ) if img else ""
    return (
        '<article class="product-card">'
        f'{img_html}'
        '<div class="product-card__body">'
        f'{disc_html}'
        f'<h3 class="product-card__title"><a href="{href}" rel="nofollow sponsored">{title}</a></h3>'
        f'<div class="product-card__price"><span class="price">${price}</span>'
        f'<span class="price--old">${original}</span></div>'
        f'<a class="btn-cta product-card__cta" href="{href}" rel="nofollow sponsored">Get deal →</a>'
        "</div></article>"
    )


def article_card_html(article: dict, site_url: str) -> str:
    slug = esc(article.get("slug", ""))
    title = esc(article.get("title", ""))
    date = esc(article.get("date", ""))
    meta_desc = esc(article.get("meta_desc", article.get("meta_description", "")))
    category = article.get("category", "")
    cat_name = CATEGORY_NAMES.get(category, category.replace("-", " ").title()) if category else ""
    img = esc(article.get("image_url", ""))
    href = f"{site_url}/en/blog/{slug}/"
    img_html = (
        f'<a href="{href}"><img class="blog-card__img" src="{img}" alt="{title}" '
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
    category_slug: str, products_by_cat: dict, site_url: str, limit: int = 4, max_price: float = None, topic_kws=None
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
    cat_name = CATEGORY_NAMES.get(category_slug, category_slug.title())
    cards = "".join(product_card_html(p, category_slug, site_url) for p in products)
    return (
        f'<section class="related-products">'
        f'<h2 class="related-products__title">Top {cat_name} deals right now</h2>'
        f'<div class="product-grid">{cards}</div>'
        f'<p class="related-products__cta">'
        f'<a class="btn-cta" href="{site_url}/en/{category_slug}/">'
        f'Browse all {cat_name} deals →</a></p>'
        f'</section>'
    )


def _extract_faq_schema(content_html: str) -> str:
    """Build FAQPage JSON-LD from <details>/<summary> pairs in blog content."""
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


def base_context(site_url: str) -> dict:
    return {
        "site_title": SITE_TITLE,
        "site_description": SITE_DESCRIPTION,
        "site_url": site_url,
        "year": str(datetime.now(timezone.utc).year),
    }


def build_home(site_url: str, flash_deals: list, articles: list) -> None:
    tpl = load_template("home.html")
    flash_html = "".join(deal_card_html(d, site_url) for d in flash_deals[:8])
    blog_html = "".join(article_card_html(a, site_url) for a in articles[:6])
    ctx = base_context(site_url)
    ctx.update({
        "canonical_url": f"{site_url}/en/",
        "flash_preview_html": flash_html or "<p>No flash deals right now.</p>",
        "blog_preview_html": blog_html or "<p>No articles yet — stay tuned.</p>",
    })
    write_file(OUTPUT_DIR / "index.html", render(tpl, ctx))


def build_categories(site_url: str, products_by_cat: dict) -> None:
    tpl = load_template("category.html")
    for slug, data in products_by_cat.items():
        products = data.get("products", [])
        ctx = base_context(site_url)
        ctx.update({
            "canonical_url": f"{site_url}/en/{slug}/",
            "category_name": CATEGORY_NAMES.get(slug, slug.title()),
            "category_slug": slug,
            "products_html": "".join(product_card_html(p, slug, site_url) for p in products),
            "products_count": str(len(products)),
            "updated_at": esc(data.get("updated_at", "")),
        })
        write_file(OUTPUT_DIR / slug / "index.html", render(tpl, ctx))


def build_products(site_url: str, products_by_cat: dict) -> None:
    tpl = load_template("product.html")
    flat = []
    for slug, data in products_by_cat.items():
        for p in data.get("products", []):
            flat.append((slug, p))
    for cat_slug, product in flat:
        related = [
            p for s, p in flat
            if s == cat_slug and p.get("product_id") != product.get("product_id")
        ][:4]
        related_html = "".join(product_card_html(p, cat_slug, site_url) for p in related)
        price_history = product.get("price_history") or [
            {"date": product.get("fetched_at", ""), "price": product.get("price", "")}
        ]
        price_history_json = (
            json.dumps(price_history, ensure_ascii=False)
            .replace('"', "&quot;")
        )
        product_slug = product.get("slug", "")
        og_image = product.get("image_url") or f"{site_url}{DEFAULT_OG_IMAGE_PATH}"
        ctx = base_context(site_url)
        ctx.update({
            "canonical_url": f"{site_url}/en/{cat_slug}/{product_slug}/",
            "title": esc(product.get("title", "")),
            "title_short": esc(short_title(product.get("title", ""), 43)),
            "meta_description": esc(meta_desc_from_product(product)),
            "category_slug": cat_slug,
            "category_name": CATEGORY_NAMES.get(cat_slug, cat_slug.title()),
            "category_particle_effect": CATEGORY_PARTICLES.get(cat_slug, "electric"),
            "slug": esc(product_slug),
            "product_id": esc(product.get("product_id", "")),
            "image_url": esc(product.get("image_url", "")),
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
            OUTPUT_DIR / cat_slug / product_slug / "index.html",
            render(tpl, ctx),
        )


def build_blog_index(site_url: str, articles: list) -> None:
    tpl = load_template("blog-index.html")
    ctx = base_context(site_url)
    ctx["canonical_url"] = f"{site_url}/en/blog/"

    RECENT_COUNT = 7
    recent_articles = articles[:RECENT_COUNT]
    older_articles = articles[RECENT_COUNT:]

    # Build archive section
    if older_articles:
        archive: dict = {}
        for a in older_articles:
            month_key = a.get("date", "")[:7]  # "2026-05"
            if month_key not in archive:
                archive[month_key] = []
            archive[month_key].append(a)

        archive_items_html = ""
        for month_key in sorted(archive.keys(), reverse=True):
            arts = archive[month_key]
            try:
                month_label = datetime.strptime(month_key, "%Y-%m").strftime("%B %Y")
            except Exception:
                month_label = month_key
            count = len(arts)
            items = ""
            for a in arts:
                slug = esc(a.get("slug", ""))
                title = esc(a.get("title", ""))
                date = esc(a.get("date", ""))
                cat = a.get("category", "")
                cat_name = CATEGORY_NAMES.get(cat, cat.replace("-", " ").title()) if cat else ""
                href = f"{site_url}/en/blog/{slug}/"
                items += f'<div class="archive-item"><a href="{href}">{title}</a><span class="archive-item__meta">{date} · {cat_name}</span></div>'
            archive_items_html += f'<div class="archive-month"><h3 class="archive-month__heading">{month_label} · {count} article{"s" if count != 1 else ""}</h3><div class="archive-list">{items}</div></div>'

        archive_section_html = f'<section class="archive-section"><h2 class="archive-section__title">Archive</h2>{archive_items_html}</section>'
    else:
        archive_section_html = ""

    ctx["articles_html"] = (
        "".join(article_card_html(a, site_url) for a in recent_articles)
        or "<p>No articles yet.</p>"
    )
    ctx["archive_section_html"] = archive_section_html
    write_file(OUTPUT_DIR / "blog" / "index.html", render(tpl, ctx))


def build_blog_posts(site_url: str, articles: list, products_by_cat: dict) -> None:
    tpl = load_template("blog-post.html")

    # Carica prodotti articolo-specifici (fetchati on-demand da fetch_products.py)
    _article_products: dict = {}
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
        related_section = related_products_section_html(
            category_slug, products_by_cat, site_url, limit=4,
            max_price=max_price, topic_kws=topic_kws
        )
        # Fallback: prodotti fetchati on-demand per articoli con topic specifico
        if not related_section and topic_kws is not None and slug in _article_products:
            related_section = related_products_section_html(
                slug, _article_products, site_url, limit=4, max_price=max_price
            )
        og_image = f"{site_url}{DEFAULT_OG_IMAGE_PATH}"
        content_html = article.get("content_html", article.get("content", ""))
        # strip any <h1> the AI may have added — template already renders the title as H1
        content_html = re.sub(r'<h1(\s[^>]*)?>', r'<h2\1>', content_html, flags=re.IGNORECASE)
        content_html = re.sub(r'</h1>', '</h2>', content_html, flags=re.IGNORECASE)
        faq_schema_html = _extract_faq_schema(content_html)
        ctx = base_context(site_url)
        ctx.update({
            "canonical_url": f"{site_url}/en/blog/{slug}/",
            "title": esc(article.get("title", "")),
            "title_short": esc(short_title(article.get("title", ""), 60)),
            "slug": esc(slug),
            "date": esc(article.get("date", "")),
            "meta_description": esc(article.get("meta_desc", article.get("meta_description", ""))),
            "content_html": content_html,
            "reading_time_min": esc(article.get("reading_time_min", 5)),
            "og_image": og_image,
            "category_slug": esc(category_slug),
            "category_name": esc(CATEGORY_NAMES.get(category_slug, category_slug.title())),
            "related_products_section": related_section,
            "faq_schema_html": faq_schema_html,
        })
        write_file(
            OUTPUT_DIR / "blog" / slug / "index.html",
            render(tpl, ctx),
        )


def build_flash_sale(site_url: str, flash_deals: list, updated_at: str) -> None:
    tpl = load_template("flash-sale.html")
    ctx = base_context(site_url)
    ctx.update({
        "canonical_url": f"{site_url}/en/flash-sale/",
        "deals_html": (
            "".join(deal_card_html(d, site_url) for d in flash_deals)
            or "<p>No flash deals right now.</p>"
        ),
        "deals_count": str(len(flash_deals)),
        "updated_at": esc(updated_at),
    })
    write_file(OUTPUT_DIR / "flash-sale" / "index.html", render(tpl, ctx))


def build_coupons(site_url: str, coupons: list, updated_at: str) -> None:
    tpl = load_template("coupon-page.html")
    ctx = base_context(site_url)
    ctx.update({
        "canonical_url": f"{site_url}/en/coupons/",
        "coupons_html": (
            "".join(coupon_card_html(c, site_url) for c in coupons)
            or "<p>No active coupons right now.</p>"
        ),
        "coupons_count": str(len(coupons)),
        "updated_at": esc(updated_at),
    })
    write_file(OUTPUT_DIR / "coupons" / "index.html", render(tpl, ctx))


def build_static_pages(site_url: str) -> None:
    for slug, title in STATIC_PAGES:
        tpl_path = TEMPLATES_DIR / f"{slug}.html"
        if not tpl_path.exists():
            print(f"  [warn] template {slug}.html missing, skip")
            continue
        tpl = tpl_path.read_text(encoding="utf-8")
        ctx = base_context(site_url)
        ctx.update({
            "canonical_url": f"{site_url}/en/{slug}/",
            "title": title,
            "lang": "en",
        })
        out_dir = OUTPUT_DIR / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(render(tpl, ctx), encoding="utf-8")
        print(f"  -> en/{slug}/index.html")


def _sitemap_priority(url: str, site_url: str) -> str:
    path = url[len(site_url):] if url.startswith(site_url) else url
    for slug in LOW_PRIORITY_PAGES:
        if path.rstrip("/").endswith(f"/en/{slug}"):
            return "0.1"
    return "0.7"


def build_sitemap(site_url: str, products_by_cat: dict, articles: list) -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    urls = [
        f"{site_url}/en/",
        f"{site_url}/en/flash-sale/",
        f"{site_url}/en/coupons/",
        f"{site_url}/en/blog/",
    ]
    for slug, _ in STATIC_PAGES:
        urls.append(f"{site_url}/en/{slug}/")
    for slug in products_by_cat:
        urls.append(f"{site_url}/en/{slug}/")
        for p in products_by_cat[slug].get("products", []):
            urls.append(f"{site_url}/en/{slug}/{p.get('slug', '')}/")
    for a in articles:
        urls.append(f"{site_url}/en/blog/{a.get('slug', '')}/")
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


def load_products() -> dict:
    out = {}
    products_dir = DATA_DIR / "products" / "en"
    if not products_dir.exists():
        return out
    for f in products_dir.glob("*.json"):
        data = load_json(f, default={"products": []})
        out[f.stem] = data
    return out


def load_articles() -> list:
    blog_dir = DATA_DIR / "blog" / "en"
    if not blog_dir.exists():
        return []
    items = []
    for f in sorted(blog_dir.glob("*.json"), reverse=True):
        data = load_json(f)
        if data:
            items.append(data)
    return items


def load_flash_deals() -> tuple:
    data = load_json(DATA_DIR / "flash-sale" / "en.json", default={})
    deals = data.get("deals", data.get("products", []))
    return deals, data.get("updated_at", "")


def load_coupons() -> tuple:
    data = load_json(DATA_DIR / "coupons" / "en.json", default={})
    coupons = data.get("coupons", data.get("products", []))
    return coupons, data.get("updated_at", "")


def clean_output() -> None:
    if OUTPUT_DIR.exists():
        for child in OUTPUT_DIR.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()


def main() -> None:
    config = load_json(CONFIG_PATH, default={})
    site_url = config.get("site_url", "https://gallo93.github.io/aliglobalshop").rstrip("/")
    print(f"[build] site_url={site_url}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    clean_output()

    products_by_cat = load_products()
    articles = load_articles()
    flash_deals, flash_updated = load_flash_deals()
    coupons, coupons_updated = load_coupons()

    print(f"[build] categories={len(products_by_cat)} articles={len(articles)} "
          f"flash={len(flash_deals)} coupons={len(coupons)}")

    build_home(site_url, flash_deals, articles)
    build_categories(site_url, products_by_cat)
    build_products(site_url, products_by_cat)
    build_blog_index(site_url, articles)
    build_blog_posts(site_url, articles, products_by_cat)
    build_flash_sale(site_url, flash_deals, flash_updated)
    build_coupons(site_url, coupons, coupons_updated)
    build_static_pages(site_url)
    build_sitemap(site_url, products_by_cat, articles)

    print("[build] done")


if __name__ == "__main__":
    main()
