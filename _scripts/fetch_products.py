"""
Fetch prodotti da AliExpress Affiliate API -> upload immagini su Cloudinary -> salva JSON.

Miglioramenti:
- Keyword specifiche per nicchia (5 ognuna)
- Score normalizzato (cap a 5000 vendite)
- Blacklist regex con word boundaries
- Filtri prezzo/sconto
- Cache API con TTL 24h (UNIX timestamp)
"""
import hashlib
import hmac
import json
import os
import re
import time
from pathlib import Path

import cloudinary
import cloudinary.uploader
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "_data" / "products" / "en"
CACHE_DIR = BASE_DIR / "_data" / "cache"
CACHE_TTL = 86400  # 24h

APP_KEY = os.getenv("ALIEXPRESS_APP_KEY", "")
APP_SECRET = os.getenv("ALIEXPRESS_APP_SECRET", "")
TRACKING_ID = os.getenv("ALIEXPRESS_TRACKING_ID", "")
API_URL = "https://api-sg.aliexpress.com/sync"

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME", ""),
    api_key=os.getenv("CLOUDINARY_API_KEY", ""),
    api_secret=os.getenv("CLOUDINARY_API_SECRET", ""),
)

NICHES = {
    "electronics": [
        "wireless earbuds bluetooth",
        "bluetooth speaker portable",
        "led strip lights smart",
        "power bank fast charging",
        "wireless charging pad",
    ],
    "smart-home": [
        "smart wifi plug",
        "smart led bulb wifi",
        "robot vacuum cleaner wifi",
        "wifi security camera indoor",
        "smart home sensor zigbee",
    ],
    "sport": [
        "fitness resistance bands set",
        "yoga mat non slip",
        "cycling accessories helmet",
        "water bottle sports insulated",
        "jump rope fitness",
    ],
    "gadgets": [
        "portable power bank 20000mah",
        "usb hub multiport",
        "magnetic phone mount car",
        "mini projector portable",
        "wireless charging pad fast",
    ],
}

BLACKLIST_PATTERNS = [re.compile(p, re.I) for p in [
    r"\bcar\b", r"\btruck\b", r"\brv\b", r"\bcamper\b", r"\bmotorcycle\b",
    r"\bshock absorber\b", r"\btrailer\b", r"\bfreezer\b", r"\bcigar\b",
    r"\bindustrial\b", r"\bforklift\b", r"\bboiler\b", r"\bautomotive\b",
]]

TYPE_PATTERNS = {
    "watch": re.compile(r"\bsmartwatch\b|\bsmart watch\b|\bwatch\b", re.I),
    "earbuds": re.compile(r"\bearbuds\b|\bearphone\b|\bheadphone\b|\bheadset\b|\bairpod", re.I),
    "phone_case": re.compile(r"\bphone case\b|\bcase.*iphone\b|\biphone.*case\b", re.I),
    "speaker": re.compile(r"\bspeaker\b", re.I),
}
MAX_PER_TYPE = 3

def cap_per_type(products: list) -> list:
    counts: dict = {}
    result = []
    for p in products:
        title = p.get("product_title", p.get("title", ""))
        ptype = None
        for t, pat in TYPE_PATTERNS.items():
            if pat.search(title):
                ptype = t
                break
        if ptype:
            if counts.get(ptype, 0) >= MAX_PER_TYPE:
                continue
            counts[ptype] = counts.get(ptype, 0) + 1
        result.append(p)
    return result

MAX_PRICE_USD = 200.0
MIN_DISCOUNT_PCT = 5.0
SALES_CAP = 5000


def _sign(params: dict) -> str:
    sorted_pairs = sorted(params.items())
    sign_str = "".join(f"{k}{v}" for k, v in sorted_pairs)
    return hmac.new(
        APP_SECRET.encode("utf-8"),
        sign_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest().upper()


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.ASCII)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:60]


def _kw_cache_key(keyword: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", keyword.lower()).strip("-")


def upload_image(image_url: str, product_id: str) -> str:
    if not image_url or "placeholder" in image_url.lower():
        return ""
    try:
        result = cloudinary.uploader.upload(
            image_url,
            public_id=f"products/{product_id}",
            format="webp",
            overwrite=False,
            resource_type="image",
            transformation=[{"width": 600, "height": 600, "crop": "limit", "quality": "auto"}],
        )
        return result["secure_url"]
    except Exception as e:
        print(f"  [WARN] image upload failed {product_id}: {e}")
        return image_url


def fetch_products(keyword: str, page_size: int = 30) -> list:
    """Fetch con cache TTL 24h."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{_kw_cache_key(keyword)}.json"

    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if time.time() - cached.get("timestamp", 0) < CACHE_TTL:
                print(f"  [cache] {keyword}")
                return cached.get("data", [])
        except Exception:
            pass

    params = {
        "app_key": APP_KEY,
        "format": "json",
        "keywords": keyword,
        "method": "aliexpress.affiliate.hotproduct.query",
        "page_no": "1",
        "page_size": str(page_size),
        "sign_method": "sha256",
        "target_currency": "USD",
        "target_language": "EN",
        "timestamp": str(int(time.time() * 1000)),
        "v": "2.0",
    }
    if TRACKING_ID:
        params["tracking_id"] = TRACKING_ID

    params["sign"] = _sign(params)

    try:
        resp = requests.get(API_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        result = (
            data.get("aliexpress_affiliate_hotproduct_query_response", {})
            .get("resp_result", {})
        )
        if result.get("resp_code") == 200:
            raw = result.get("result", {}).get("products", {}).get("product", [])
            try:
                cache_file.write_text(
                    json.dumps({"timestamp": time.time(), "data": raw}, ensure_ascii=False),
                    encoding="utf-8",
                )
            except Exception as e:
                print(f"  [WARN] cache write failed: {e}")
            return raw
        print(f"  [WARN] API error {result.get('resp_code')}: {result.get('resp_msg')}")
        return []
    except Exception as e:
        print(f"  [ERROR] fetch failed for '{keyword}': {e}")
        return []


def _parse_float(value, default=0.0) -> float:
    try:
        if value is None:
            return default
        return float(str(value).replace(",", "").replace("%", "").strip() or default)
    except (ValueError, TypeError):
        return default


def _parse_int(value, default=0) -> int:
    try:
        if value is None:
            return default
        return int(float(str(value).replace(",", "").strip() or default))
    except (ValueError, TypeError):
        return default


def score_product(p: dict) -> float:
    sales = min(_parse_int(p.get("lastest_volume") or p.get("volume", 0)), SALES_CAP)
    discount = _parse_float(p.get("discount", "0"))
    rating_raw = _parse_float(p.get("evaluate_rate", "0"))
    rating = rating_raw / 20.0  # 0-100% -> 0-5
    return (sales / SALES_CAP * 0.6) + (discount / 100.0 * 0.3) + (rating / 5.0 * 0.1)


def is_blacklisted(title: str) -> bool:
    return any(p.search(title) for p in BLACKLIST_PATTERNS)


def build_product(raw: dict, niche: str, hosted_image: str) -> dict:
    product_id = str(raw.get("product_id", ""))
    title = raw.get("product_title", "")
    discount_pct = _parse_int(str(raw.get("discount", "0")).strip("%"))
    rating_raw = _parse_float(str(raw.get("evaluate_rate", "0")).strip("%"))
    rating = round(rating_raw / 20.0, 1) if rating_raw else None
    price = _parse_float(raw.get("target_sale_price") or raw.get("sale_price", "0"))
    original = _parse_float(raw.get("target_original_price") or raw.get("original_price", price))

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "product_id": product_id,
        "title": title,
        "slug": slugify(title),
        "price": round(price, 2) if price else raw.get("target_sale_price"),
        "original_price": round(original, 2) if original else raw.get("target_original_price"),
        "discount_pct": discount_pct,
        "affiliate_url": raw.get("promotion_link") or raw.get("product_detail_url", ""),
        "image_url": hosted_image,
        "category": niche,
        "rating": rating,
        "reviews_count": _parse_int(raw.get("lastest_volume", 0)),
        "sales_volume": _parse_int(raw.get("lastest_volume") or raw.get("volume", 0)),
        "score": round(score_product(raw), 4),
        "price_history": [],
        "fetched_at": now,
        "updated_at": now,
    }


_ARTICLE_TOPIC_PATTERNS = [
    re.compile(r'\bearbuds?\b|\bearphones?\b|\bheadphones?\b|\bheadset\b|\btws\b|\bairpods?\b', re.I),
    re.compile(r'\bvacuum\b', re.I),
    re.compile(
        r'\bbulbs?\b|\blamps?\b|\bdownlights?\b|\bspotlights?\b|\bchandeliers?\b|'
        r'\b(?:down|ceiling|pendant|spot|led)\s+lights?\b',
        re.I,
    ),
    re.compile(
        r'\bsmartwatche?s?\b|\bsmart\s+watch\b|\bsmartband\b|\bfitness\s+tracker\b|\bwristwatch\b',
        re.I,
    ),
    re.compile(
        r'\bhome\s+gym\b|\bgym\s+(?:equipment|bench|stall)\b|\bdumbbell\b|\bbarbell\b|'
        r'\bkettlebell\b|\btreadmill\b|\bpull[\s-]?up\b|\bsit[\s-]?up\b|'
        r'\bswedish\s+ladder\b|\bweight(?:lifting|s)?\b|\bfitness\s+equipment\b',
        re.I,
    ),
]

# Parole rumore rimosse dalla keyword di ricerca per renderla pertinente
_KW_STOPWORDS = {
    "aliexpress", "reviews", "review", "guide", "guides", "best", "top",
    "picks", "pick", "under", "the", "a", "an", "and", "or", "for",
    "with", "vs", "2024", "2025", "2026", "2027",
}

# Termini che indicano un ACCESSORIO/ricambio, non il dispositivo vero e proprio.
# pad/pads e strap esclusi di proposito: i robot vacuum legittimi hanno 'mop pad'
# e gli smartwatch veri hanno 'strap/band' nel titolo.
# stickers/labels/sealing/packing/wrapping/seal box: materiale da imballo.
# 'wrap' secco escluso di proposito: 'hand/wrist/knee wrap' sono attrezzi gym veri.
_ACCESSORY_PATTERN = re.compile(
    r'\b(?:case|cover|pouch|cushion|foam|sponge|tips?|eartips?|ear\s+tips?|'
    r'holder|stand|skin|stickers?|labels?|sealing|packing|wrapping|seal\s+box|'
    r'protector|screen\s+protector|replacement|spare|'
    r'battery|charger|dock|cable|glass|lens|bumper|crystal|repair|accessor(?:y|ies))\b',
    re.I,
)

# Categorie adiacenti off-topic da scartare negli article-products.
# 'board' MAI da solo (spezzerebbe 'sit-up board'/'supine board' del home-gym):
# solo dopo decoder/receiver/audio/circuit/bluetooth.
# 'box' ristretto (watch/storage/jewelry/jewellery/display/gift) per non colpire
# 'charging box' degli earbuds ne 'plyo box'/'jump box' del gym.
_OFFTOPIC_PATTERN = re.compile(
    r'\bpower\s*bank\b|\bpowerbank\b|\btransmitter\b|\breceiver\b|\bdecoder\b|'
    r'\b(?:decoder|receiver|audio|circuit|bluetooth)\s+board\b|'
    r'\badapter\b|\bmodule\b|\bsafe\b|\bcabinet\b|\bstorage\b|\bwinder\b|\borganizer\b|'
    r'\b(?:watch|storage|jewelry|jewellery|display|gift)\s+box\b',
    re.I,
)


def _clean_search_kw(text: str) -> str:
    """Deriva una keyword di ricerca pertinente rimuovendo parole rumore,
    anni e cifre (es. prezzi) dal primary_keyword/title."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    kept = [w for w in words if w not in _KW_STOPWORDS and not w.isdigit()]
    return " ".join(kept).strip()


def _is_relevant(title: str, topic_pattern) -> bool:
    """Pertinente solo se il titolo matcha il pattern-tema (core) dell'articolo."""
    return bool(title) and topic_pattern is not None and bool(topic_pattern.search(title))


def _is_accessory(title: str) -> bool:
    """True se il titolo indica un accessorio/ricambio invece del dispositivo."""
    return bool(title) and bool(_ACCESSORY_PATTERN.search(title))


def _is_offtopic(title: str) -> bool:
    """True se il titolo appartiene a una categoria adiacente fuori tema."""
    return bool(title) and bool(_OFFTOPIC_PATTERN.search(title))


def fetch_article_products(blog_dir: Path, article_output_dir: Path) -> None:
    if not blog_dir.exists():
        return
    article_output_dir.mkdir(parents=True, exist_ok=True)
    for article_file in sorted(blog_dir.glob("*.json")):
        try:
            article = json.loads(article_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        slug = article.get("slug", "")
        primary_kw = article.get("primary_keyword", "")
        title = article.get("title", "")
        combined = f"{title} {primary_kw}"
        if not slug or not primary_kw:
            continue
        topic_pattern = next(
            (pat for pat in _ARTICLE_TOPIC_PATTERNS if pat.search(combined)),
            None,
        )
        if topic_pattern is None:
            continue
        cache_file = article_output_dir / f"{slug}.json"
        if cache_file.exists():
            try:
                cached = json.loads(cache_file.read_text(encoding="utf-8"))
                if time.time() - cached.get("timestamp", 0) < CACHE_TTL:
                    print(f"  [article cache] {slug}")
                    continue
            except Exception:
                pass

        search_kw = _clean_search_kw(primary_kw) or _clean_search_kw(title)
        print(f"  [article fetch] {slug} -- search kw: '{search_kw}'")
        raw = fetch_products(search_kw, page_size=30)
        if not raw:
            print(f"  [WARN] nessun risultato API per '{slug}' (kw: {search_kw})")
            continue

        relevant = [
            r for r in raw
            if not is_blacklisted(r.get("product_title", ""))
            and not _is_accessory(r.get("product_title", ""))
            and not _is_offtopic(r.get("product_title", ""))
            and _is_relevant(r.get("product_title", ""), topic_pattern)
        ]
        relevant.sort(key=score_product, reverse=True)

        products = []
        seen_ids = set()
        for r in relevant:
            if len(products) >= 6:
                break
            product_id = str(r.get("product_id", ""))
            if not product_id or product_id in seen_ids:
                continue
            seen_ids.add(product_id)
            image_url = r.get("product_main_image_url", "")
            hosted = upload_image(image_url, f"art-{product_id}") if image_url else ""
            products.append(build_product(r, article.get("category", ""), hosted))
            time.sleep(0.1)

        if len(products) < 2:
            print(f"  [WARN] <2 prodotti pertinenti per '{slug}' -- sezione related vuota")
            products = []

        data = {
            "timestamp": time.time(),
            "slug": slug,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "products": products,
        }
        cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  -> {len(products)} prodotti pertinenti per articolo {slug}")
        time.sleep(0.5)


def fetch_niche(niche: str, keywords: list) -> list:
    seen_ids = set()
    raw_pool = []
    for kw in keywords:
        print(f"  keyword: {kw}")
        raw_pool.extend(fetch_products(kw))
        time.sleep(0.3)

    filtered = []
    for p in raw_pool:
        pid = str(p.get("product_id", ""))
        if not pid or pid in seen_ids:
            continue
        title = p.get("product_title", "")
        if not title or is_blacklisted(title):
            continue
        image_url = p.get("product_main_image_url", "")
        if not image_url or "placeholder" in image_url.lower():
            continue

        price = _parse_float(p.get("target_sale_price") or p.get("sale_price", "0"))
        if price <= 0 or price > MAX_PRICE_USD:
            continue
        discount_pct = _parse_float(str(p.get("discount", "0")).strip("%"))
        if discount_pct < MIN_DISCOUNT_PCT:
            continue

        seen_ids.add(pid)
        filtered.append(p)

    scored = cap_per_type(sorted(filtered, key=score_product, reverse=True))[:20]
    return scored


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not APP_KEY or not APP_SECRET:
        raise SystemExit("[ERROR] ALIEXPRESS_APP_KEY / ALIEXPRESS_APP_SECRET mancanti in .env")

    for niche, keywords in NICHES.items():
        print(f"\n[{niche}] fetching {len(keywords)} keywords...")
        top = fetch_niche(niche, keywords)
        products = []
        for raw in top:
            product_id = str(raw.get("product_id", ""))
            image_url = raw.get("product_main_image_url", "")
            hosted = upload_image(image_url, product_id) if image_url else ""
            products.append(build_product(raw, niche, hosted))
            time.sleep(0.2)

        output = {
            "niche": niche,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "products": products,
        }
        out_path = OUTPUT_DIR / f"{niche}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"  -> {len(products)} prodotti -> {out_path}")
        time.sleep(1)

    print("\n[article products] fetching article-specific products...")
    fetch_article_products(
        BASE_DIR / "_data" / "blog" / "en",
        OUTPUT_DIR / "_article",
    )


if __name__ == "__main__":
    main()
