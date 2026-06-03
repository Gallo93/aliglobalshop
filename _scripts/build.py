"""
Static site generator for AliGlobalShop EN.

Reads JSON in _data/ + templates in _templates/, writes HTML in en/.
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
OUTPUT_DIR = BASE_DIR / "en"
CONFIG_PATH = DATA_DIR / "config.json"

SITE_TITLE = "AliGlobalShop"
SITE_DESCRIPTION = (
    "Curated AliExpress deals, live flash sales and working coupons, updated every day."
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

CATEGORY_SEO = {
    "electronics": {
        "h1": "Best Electronics Deals on AliExpress",
        "intro": "<p>From wireless earbuds and Bluetooth speakers to LED strip lights and fast-charging power banks, our Electronics section brings you the highest-rated gadgets on AliExpress, hand-picked and updated every day. Every product is scored by sales volume, discount percentage, and buyer ratings so you always see the best value first. Prices are refreshed every 24 hours and all items include international shipping with AliExpress Buyer Protection.</p>",
        "guide_h2": "How to Pick the Best Electronics on AliExpress",
        "guide_body": "<p>Sort by discount first to spot deals where the original price has been cut 30% or more. Check the seller rating: anything above 97% positive feedback is a reliable indicator of quality. For electronics, prioritize items with at least 500 reviews, since a large review base means real-world testing by buyers in your country.</p><p>Pay attention to compatibility details. Verify that chargers list 100-240 V input (universal voltage) and that wireless devices state the Bluetooth version. Items with detailed specification tables and real buyer photos in the reviews are usually worth the extra minute of research before purchasing.</p>",
        "faq_h2": "Electronics on AliExpress: Common Questions",
        "faqs": [
            ("Are AliExpress electronics reliable?", "Quality varies by seller. Stick to shops with 97%+ positive ratings and at least 1,000 orders. Most top-ranked electronics come with a 12-month warranty and Buyer Protection that covers returns if the item does not match the description."),
            ("How long does electronics shipping take?", "Standard shipping from China takes 10-25 days to most countries. Many sellers offer AliExpress Standard Shipping in 7-15 days. Delivery times have improved significantly for US, UK, and EU buyers in 2025-2026."),
            ("Can I return electronics bought on AliExpress?", "Yes. AliExpress Buyer Protection covers disputes for up to 15 days after delivery. Open a dispute in the app if the item arrives damaged or not as described, and AliExpress will mediate a refund or replacement."),
        ],
    },
    "smart-home": {
        "h1": "Best Smart Home Deals on AliExpress",
        "intro": "<p>Automate your home without the premium price tag. Our Smart Home section covers Wi-Fi plugs, LED smart bulbs, robot vacuums, indoor security cameras, and Zigbee sensors, all sourced from top-rated AliExpress sellers and updated daily. Whether you run a Google Home, Amazon Alexa, or Apple HomeKit setup, you will find compatible devices here at a fraction of retail cost. Every product includes verified ratings and current pricing updated every 24 hours.</p>",
        "guide_h2": "How to Build a Smart Home with AliExpress Devices",
        "guide_body": "<p>Start with a smart plug or a Wi-Fi bulb: both are under $10 and work with every major voice assistant. Once you are comfortable with the app, expand to sensors and cameras. Zigbee devices require a hub (often $15-25) but offer better battery life and local processing than Wi-Fi-only alternatives for larger setups.</p><p>Always check the app name in the product description. Most AliExpress smart home devices use the Tuya Smart or Smart Life app, which integrates with Alexa, Google Home, and Apple Home via third-party bridges. Avoid products with no app name listed in the specifications.</p>",
        "faq_h2": "Smart Home on AliExpress: Common Questions",
        "faqs": [
            ("Do AliExpress smart home devices work with Alexa and Google Home?", "Most do, through the Tuya Smart platform. Look for 'Works with Alexa' or 'Google Home compatible' in the product title or description. Setup usually takes under 5 minutes once the device is paired with the Tuya Smart app."),
            ("Are AliExpress smart devices safe to use on my Wi-Fi network?", "Place them on a dedicated IoT Wi-Fi network to isolate them from your main devices, since most modern routers support this. Reputable sellers use standard Tuya firmware with regular security updates."),
            ("What smart home hub works best with AliExpress Zigbee devices?", "The Sonoff Zigbee 3.0 USB Dongle Plus, also available on AliExpress, is a popular low-cost hub compatible with Home Assistant. For Wi-Fi devices, no hub is needed at all."),
        ],
    },
    "sport": {
        "h1": "Best Sport &amp; Fitness Deals on AliExpress",
        "intro": "<p>Equip your workouts without overspending. Our Sport section features resistance bands, non-slip yoga mats, cycling accessories, insulated water bottles, and jump ropes from top-rated AliExpress sellers, ranked by sales volume, discount, and buyer satisfaction. All items ship internationally and are covered by AliExpress Buyer Protection. The product list is refreshed every 24 hours so the prices and availability you see are always current.</p>",
        "guide_h2": "How to Buy Sport Equipment on AliExpress",
        "guide_body": "<p>For resistance bands and yoga mats, check the material specification: natural latex bands last significantly longer than TPE alternatives. Yoga mats should list thickness (6 mm or more is ideal) and surface texture. Seller photos showing real use and close-ups of the material are a good sign of a trustworthy listing.</p><p>Cycling gear and helmets require special attention to sizing. Most AliExpress listings include detailed size charts, so measure your head circumference before ordering. For safety-critical items like helmets, confirm that the listing mentions CE or CPSC certification in the product description.</p>",
        "faq_h2": "Sport &amp; Fitness on AliExpress: Common Questions",
        "faqs": [
            ("Are AliExpress resistance bands worth buying?", "Yes, especially for home workouts. Bands from top sellers with 4.5+ ratings and 1,000+ orders are durable and match gym-branded alternatives at 3-5x the price. Look for natural latex material and a set with multiple resistance levels."),
            ("Can I trust AliExpress helmet safety ratings?", "Check for CE EN1078 (EU) or CPSC (US) certification mentioned in the product description. Listings with official certification logos and test report photos are generally reliable. Avoid helmets with no certification information listed."),
            ("What is the return policy for sport equipment on AliExpress?", "AliExpress Buyer Protection covers items that arrive damaged or not as described within 15 days of delivery. Photograph everything at unboxing to have evidence for any dispute, especially for larger items."),
        ],
    },
    "gadgets": {
        "h1": "Best Gadgets &amp; Tech Deals on AliExpress",
        "intro": "<p>Discover the latest tech accessories and everyday carry essentials at unbeatable prices. Our Gadgets section features high-capacity power banks, multi-port USB hubs, magnetic phone mounts, mini projectors, and wireless charging pads, sourced from verified AliExpress sellers and refreshed daily. Every product is ranked by real buyer ratings and sales volume so the most popular picks surface first. All items include AliExpress Buyer Protection and international shipping.</p>",
        "guide_h2": "How to Find the Best Gadgets on AliExpress",
        "guide_body": "<p>For power banks, check the actual capacity in watt-hours (Wh) rather than the milliamp-hour (mAh) claim alone, as voltage conversion means a 20,000 mAh bank at 3.7 V delivers about 74 Wh. Fast charging support (18W, 20W, or 33W) is worth a few extra dollars for significantly faster top-ups.</p><p>USB hubs and multi-port chargers should list individual port wattage. A hub advertising 100W shared across 4 ports may only deliver 18W per port. Check the detailed spec table or the verified Q&amp;A section for real output figures before purchasing.</p>",
        "faq_h2": "Gadgets on AliExpress: Common Questions",
        "faqs": [
            ("Are AliExpress power banks allowed on planes?", "Most airlines allow power banks up to 100 Wh in carry-on luggage without approval. A 20,000 mAh at 3.7 V bank is approximately 74 Wh, within the standard limit. Always check your airline's policy before travelling."),
            ("Do AliExpress gadgets come with a warranty?", "Most top-rated sellers offer a 12-month warranty and respond to after-sales issues through the AliExpress messaging system. Buyer Protection provides an additional safety net for the first 15 days after delivery."),
            ("What USB-C gadgets are compatible with iPhone 15 and newer?", "All iPhone 15 and later models use USB-C, so any USB-C hub, charger, or cable on AliExpress will be physically compatible. For fast charging, look for USB Power Delivery (PD) support with at least 20W output."),
        ],
    },
}

FLASH_SALE_FAQ = [
    ("Do flash sale prices include free shipping?", "Most flash sale items offer free standard shipping (10-20 days). AliExpress Standard Shipping (7-15 days) is included on many deals. Expedited options are usually available for an extra fee shown on the product page."),
    ("Can I return a flash sale item?", "Yes. AliExpress Buyer Protection applies to all purchases regardless of whether the item was on sale. Open a dispute within 15 days of delivery if the item is not as described or arrives damaged."),
    ("How often are flash sale deals updated?", "This page is refreshed daily. AliExpress itself rotates flash sale inventory continuously, so returning throughout the day may reveal new deals not available at your last visit."),
]

COUPONS_FAQ = [
    ("Do I need a coupon code for these discounts?", "No. All discounts shown on this page are applied automatically at checkout. The reduced price is already active on the product page, so clicking our link takes you directly to the discounted listing."),
    ("Are these discounts available in all countries?", "Most AliExpress discounts are global, but prices may vary slightly by region due to currency conversion and local promotions. Shipping costs and availability depend on your delivery country."),
    ("How do I find even more discounts on AliExpress?", "Check the AliExpress app daily for free platform coupons in the Coupons section. New user coupons offer up to $24 off first orders. Seller coupons appear on individual shop pages and can be stacked with existing discounts."),
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


def alt_text(title: str, limit: int = 125) -> str:
    """Alt text trimmed to a word boundary, never cutting a word in half."""
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


def meta_desc_from_product(product: dict) -> str:
    base = product.get("title", "")
    price = product.get("price")
    disc = product.get("discount_pct") or 0
    text = f"{base}: only ${price} on AliExpress"
    if disc:
        text += f" (-{disc}%)"
    return short_title(text, 155)


def product_card_html(product: dict, category_slug: str, site_url: str) -> str:
    href = f"{site_url}/en/{category_slug}/{esc(product.get('slug', ''))}/"
    img = esc(product.get("image_url", ""))
    title = esc(product.get("title", ""))
    alt = esc(alt_text(product.get("title", "")))
    price = esc(product.get("price", ""))
    original = esc(product.get("original_price", ""))
    disc = product.get("discount_pct") or 0
    rating = product.get("rating") or 0
    reviews = product.get("reviews_count") or 0
    disc_html = f'<span class="price--off">-{int(disc)}%</span>' if disc else ""
    return (
        '<article class="product-card">'
        f'<a href="{href}" class="product-card__img">'
        f'<img src="{img}" alt="{alt}" width="300" height="300" loading="lazy" decoding="async"></a>'
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
        f'<div class="product-card__price"><span class="price">${price}</span>'
        f'<span class="price--old">${original}</span>{disc_html}</div>'
        f'<p class="product-card__meta">Ends in: {countdown}</p>'
        f'<a class="btn-cta product-card__cta" href="{href}"{link_rel}>Grab it →</a>'
        "</div></article>"
    )


def coupon_card_html(coupon: dict, site_url: str) -> str:
    img = esc(coupon.get("image_url", ""))
    title = esc(coupon.get("title", ""))
    alt = esc(alt_text(coupon.get("title", "")))
    price = esc(coupon.get("price", ""))
    original = esc(coupon.get("original_price", ""))
    disc = coupon.get("discount_pct") or 0
    href = esc(coupon.get("affiliate_url", f"{site_url}/en/coupons/"))
    disc_html = f'<span class="coupon-badge">-{int(disc)}% OFF</span>' if disc else ""
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
    alt = esc(alt_text(article.get("title", "")))
    href = f"{site_url}/en/blog/{slug}/"
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


def _build_faq_schema(faqs: list) -> str:
    items = [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
        for q, a in faqs
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
        "blog_preview_html": blog_html or "<p>No articles yet, stay tuned.</p>",
    })
    write_file(OUTPUT_DIR / "index.html", render(tpl, ctx))


def build_categories(site_url: str, products_by_cat: dict) -> None:
    tpl = load_template("category.html")
    for slug, data in products_by_cat.items():
        products = data.get("products", [])
        ctx = base_context(site_url)
        seo = CATEGORY_SEO.get(slug, {})
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
            "canonical_url": f"{site_url}/en/{slug}/",
            "category_name": CATEGORY_NAMES.get(slug, slug.title()),
            "category_slug": slug,
            "category_h1": seo.get("h1", f"{CATEGORY_NAMES.get(slug, slug.title())} Deals on AliExpress"),
            "category_intro_html": seo.get("intro", ""),
            "category_guide_html": guide_html,
            "faq_schema_html": _build_faq_schema(faqs) if faqs else "",
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


def related_articles_section_html(current: dict, articles: list, site_url: str, limit: int = 3) -> str:
    """Pick related articles: same category first, then most recent, excluding self."""
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
    cards = "".join(article_card_html(a, site_url) for a in picked)
    return (
        '<section class="related-articles">'
        '<h2 class="related-articles__title">Related articles</h2>'
        f'<div class="grid grid--posts">{cards}</div>'
        '</section>'
    )


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
        # Priorita' ai prodotti articolo-specifici (curati a tema dal fetch),
        # categoria come fallback.
        related_section = ""
        if slug in _article_products and _article_products[slug].get("products"):
            related_section = related_products_section_html(
                slug, _article_products, site_url, limit=4, max_price=max_price
            )
        if not related_section:
            related_section = related_products_section_html(
                category_slug, products_by_cat, site_url, limit=4,
                max_price=max_price, topic_kws=topic_kws
            )
        og_image = f"{site_url}{DEFAULT_OG_IMAGE_PATH}"
        content_html = article.get("content_html", article.get("content", ""))
        # strip any <h1> the AI may have added, since the template already renders the title as H1
        content_html = re.sub(r'<h1(\s[^>]*)?>', r'<h2\1>', content_html, flags=re.IGNORECASE)
        content_html = re.sub(r'</h1>', '</h2>', content_html, flags=re.IGNORECASE)
        faq_schema_html = _extract_faq_schema(content_html)
        related_articles_html = related_articles_section_html(article, articles, site_url, limit=3)
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
            "related_articles_html": related_articles_html,
            "faq_schema_html": faq_schema_html,
        })
        write_file(
            OUTPUT_DIR / "blog" / slug / "index.html",
            render(tpl, ctx),
        )


def build_flash_sale(site_url: str, flash_deals: list, updated_at: str) -> None:
    tpl = load_template("flash-sale.html")
    ctx = base_context(site_url)
    flash_guide_html = (
        '<h2>How AliExpress Flash Sales Work</h2>'
        '<p>Flash sale prices are set for a fixed window, usually 24-72 hours. Once the timer hits zero, the product returns to its regular price. The discount is applied automatically at checkout with no coupon code needed. Some items sell out before the timer expires if demand is high, so acting within the first few hours maximizes your chances.</p>'
        '<p>Combine flash sale prices with AliExpress platform coupons collected in the app for extra savings. A $5 platform coupon stacked on top of a 40% flash sale discount can bring the effective price well below what you would find anywhere else online.</p>'
        '<h2>Flash Sale: Common Questions</h2>'
        '<div class="faq">'
        + "".join(
            f'<details><summary>{q}</summary><p>{a}</p></details>'
            for q, a in FLASH_SALE_FAQ
        )
        + "</div>"
    )
    ctx.update({
        "canonical_url": f"{site_url}/en/flash-sale/",
        "deals_html": (
            "".join(deal_card_html(d, site_url) for d in flash_deals)
            or "<p>No flash deals right now.</p>"
        ),
        "deals_count": str(len(flash_deals)),
        "updated_at": esc(updated_at),
        "flash_intro_html": "<p>AliExpress flash sales offer steep discounts on popular products for a limited time only. Every deal on this page includes a live countdown timer so you know exactly how long the price holds. Our list is refreshed automatically, pulling only items with a verified discount of 30% or more, a minimum 4-star rating, and proven sales volume. Bookmark this page or check back daily to catch the best drops before they expire.</p>",
        "flash_guide_html": flash_guide_html,
        "faq_schema_html": _build_faq_schema(FLASH_SALE_FAQ),
    })
    write_file(OUTPUT_DIR / "flash-sale" / "index.html", render(tpl, ctx))


def build_coupons(site_url: str, coupons: list, updated_at: str) -> None:
    tpl = load_template("coupon-page.html")
    ctx = base_context(site_url)
    coupons_guide_html = (
        '<h2>How AliExpress Discounts Work</h2>'
        '<p>AliExpress offers several types of savings: seller coupons (applied per shop), platform coupons (collected in the app and valid store-wide), and SuperDeals (permanent deep discounts that do not expire). The products on this page primarily feature SuperDeals and high-discount listings where the reduced price is the standard sale price, not a short-term flash promotion.</p>'
        '<p>To maximize savings, collect free platform coupons in the AliExpress app before checkout. A $3-5 platform coupon stacked on top of an already-discounted product can save you more than buying a flash sale item without a coupon.</p>'
        '<h2>AliExpress Discounts: Common Questions</h2>'
        '<div class="faq">'
        + "".join(
            f'<details><summary>{q}</summary><p>{a}</p></details>'
            for q, a in COUPONS_FAQ
        )
        + "</div>"
    )
    ctx.update({
        "canonical_url": f"{site_url}/en/coupons/",
        "coupons_html": (
            "".join(coupon_card_html(c, site_url) for c in coupons)
            or "<p>No active coupons right now.</p>"
        ),
        "coupons_count": str(len(coupons)),
        "updated_at": esc(updated_at),
        "coupons_intro_html": "<p>Every product listed here has been marked down 50% or more from its original price, with the discount applied automatically when you reach checkout, no code needed. Our selection is curated from AliExpress SuperDeals and high-discount listings, hand-checked for verified seller ratings and genuine price reductions. The list is refreshed daily so the savings you see are always current, never outdated promotions from weeks ago.</p>",
        "coupons_guide_html": coupons_guide_html,
        "faq_schema_html": _build_faq_schema(COUPONS_FAQ),
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
    for a in articles:
        urls.append(f"{site_url}/en/blog/{a.get('slug', '')}/")
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


def build_404(site_url: str) -> None:
    tpl = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <link rel="icon" href="{{site_url}}/assets/img/favicon.svg" type="image/svg+xml">
  <link rel="icon" href="{{site_url}}/assets/img/favicon.ico" sizes="any">
  <link rel="apple-touch-icon" href="{{site_url}}/assets/img/apple-touch-icon.png">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Page not found | {{site_title}}</title>
  <meta name="description" content="The page you were looking for does not exist or has moved.">
  <meta name="robots" content="noindex">
  <link rel="canonical" href="{{site_url}}/en/">
  <link rel="stylesheet" href="{{site_url}}/assets/css/style.css">
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  <header class="nav">
    <div class="nav__inner">
      <a class="nav__logo" href="{{site_url}}/en/"><img src="{{site_url}}/assets/img/logo.svg" alt="{{site_title}}" width="240" height="40" loading="eager"></a>
      <nav class="nav__links" aria-label="Primary">
        <a href="{{site_url}}/en/electronics/">&#128241; Electronics</a>
        <a href="{{site_url}}/en/smart-home/">&#127968; Smart Home</a>
        <a href="{{site_url}}/en/sport/">&#127939; Sport</a>
        <a href="{{site_url}}/en/gadgets/">&#127918; Gadgets</a>
        <a href="{{site_url}}/en/flash-sale/">&#9889; Flash Sale</a>
        <a href="{{site_url}}/en/coupons/">&#127991; Top Discounts</a>
        <a href="{{site_url}}/en/blog/">&#128221; Blog</a>
      </nav>
      <button class="nav__hamburger" aria-label="Open menu" aria-expanded="false">
        <span></span><span></span><span></span>
      </button>
    </div>
  </header>

  <main class="container" id="main">
    <div class="legal-page">
      <h1>Page not found</h1>
      <p>Sorry, the page you were looking for does not exist or has moved. The deal may have expired, or the link might be broken.</p>
      <p><a class="btn-cta" href="{{site_url}}/en/">Back to homepage &#8594;</a></p>
      <h2>Browse our categories</h2>
      <nav>
        <p><a href="{{site_url}}/en/electronics/">&#128241; Electronics</a></p>
        <p><a href="{{site_url}}/en/smart-home/">&#127968; Smart Home</a></p>
        <p><a href="{{site_url}}/en/sport/">&#127939; Sport</a></p>
        <p><a href="{{site_url}}/en/gadgets/">&#127918; Gadgets</a></p>
      </nav>
    </div>
  </main>

  <footer class="footer">
    <div class="footer__cols container">
      <div class="footer__brand">
        <a href="{{site_url}}/en/"><strong>AliGlobal<span>Shop</span></strong></a>
        <p>A reader-supported deal aggregator for AliExpress. We earn a small commission when you buy, at no extra cost to you.</p>
      </div>
      <div class="footer__col">
        <h4>Shop</h4>
        <nav>
          <a href="{{site_url}}/en/electronics/">&#128241; Electronics</a>
          <a href="{{site_url}}/en/smart-home/">&#127968; Smart Home</a>
          <a href="{{site_url}}/en/sport/">&#127939; Sport</a>
          <a href="{{site_url}}/en/gadgets/">&#127918; Gadgets</a>
        </nav>
      </div>
      <div class="footer__col">
        <h4>Save</h4>
        <nav>
          <a href="{{site_url}}/en/flash-sale/">&#9889; Flash Sale</a>
          <a href="{{site_url}}/en/coupons/">&#127991; Top Discounts</a>
        </nav>
      </div>
      <div class="footer__col">
        <h4>Info</h4>
        <nav>
          <a href="{{site_url}}/en/blog/">&#128221; Blog</a>
          <a href="{{site_url}}/en/about/">About</a>
          <a href="{{site_url}}/en/contact/">Contact</a>
          <a href="{{site_url}}/en/privacy/">Privacy</a>
        </nav>
      </div>
    </div>
    <div class="footer__bottom">
      <div class="container">
        <p>&copy; {{year}} {{site_title}}. Affiliate disclosure: we earn commissions from qualifying AliExpress purchases.</p>
      </div>
    </div>
  </footer>
  <script defer src="{{site_url}}/assets/js/main.js"></script>
</body>
</html>
"""
    write_file(BASE_DIR / "404.html", render(tpl, base_context(site_url)))


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
    site_url = config.get("site_url", "https://aliglobalshop.net").rstrip("/")
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
    build_robots(site_url)
    build_404(site_url)

    print("[build] done")


if __name__ == "__main__":
    main()
