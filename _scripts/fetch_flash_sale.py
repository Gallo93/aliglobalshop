"""
Fetch prodotti flash-sale da AliExpress Affiliate API — keyword per nicchia.
Output: _data/flash-sale/en.json con campo 'expires_at' = now + 3600s.
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
OUTPUT_DIR = BASE_DIR / "_data" / "flash-sale"

APP_KEY = os.getenv("ALIEXPRESS_APP_KEY", "")
APP_SECRET = os.getenv("ALIEXPRESS_APP_SECRET", "")
TRACKING_ID = os.getenv("ALIEXPRESS_TRACKING_ID", "")
API_URL = "https://api-sg.aliexpress.com/sync"

KEYWORDS = [
    "wireless earbuds discount",
    "smart home gadgets sale",
    "fitness tracker deal",
    "portable bluetooth speaker",
    "led strip lights rgb",
]
TOP_N = 10
MAX_PRICE_USD = 150.0
MIN_DISCOUNT_PCT = 20
EXPIRES_IN_SECONDS = 3600

BLACKLIST_PATTERNS = [re.compile(p, re.I) for p in [
    r"\bcar\b", r"\btruck\b", r"\brv\b", r"\bcamper\b", r"\bmotorcycle\b",
    r"\bshock absorber\b", r"\btrailer\b", r"\bfreezer\b", r"\bcigar\b",
    r"\bindustrial\b", r"\bforklift\b", r"\bboiler\b", r"\bautomotive\b",
    r"\bsteel\b", r"\bgalvalume\b", r"\bcoil\b", r"\bplate\b",
]]

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME", ""),
    api_key=os.getenv("CLOUDINARY_API_KEY", ""),
    api_secret=os.getenv("CLOUDINARY_API_SECRET", ""),
)


def _sign(params: dict) -> str:
    sorted_pairs = sorted(params.items())
    sign_str = "".join(f"{k}{v}" for k, v in sorted_pairs)
    return hmac.new(APP_SECRET.encode("utf-8"), sign_str.encode("utf-8"), hashlib.sha256).hexdigest().upper()


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.ASCII)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:60]


def _parse_float(value, default=0.0) -> float:
    try:
        return float(str(value).replace(",", "").replace("%", "").strip() or default)
    except (ValueError, TypeError):
        return default


def _parse_int(value, default=0) -> int:
    try:
        return int(float(str(value).replace(",", "").strip() or default))
    except (ValueError, TypeError):
        return default


def is_blacklisted(title: str) -> bool:
    return any(p.search(title) for p in BLACKLIST_PATTERNS)


def upload_image(image_url: str, product_id: str) -> str:
    if not image_url or "placeholder" in image_url.lower():
        return image_url
    try:
        result = cloudinary.uploader.upload(
            image_url,
            public_id=f"flash-sale/{product_id}",
            format="webp",
            overwrite=False,
            resource_type="image",
            transformation=[{"width": 600, "height": 600, "crop": "limit", "quality": "auto"}],
        )
        return result["secure_url"]
    except Exception as e:
        print(f"  [WARN] image upload failed {product_id}: {e}")
        return image_url


def fetch_hot_products(keyword: str, page_size: int = 30) -> list:
    params = {
        "app_key": APP_KEY,
        "format": "json",
        "keywords": keyword,
        "method": "aliexpress.affiliate.hotproduct.query",
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
            return result.get("result", {}).get("products", {}).get("product", [])
        print(f"  [WARN] API error {result.get('resp_code')}: {result.get('resp_msg')}")
        return []
    except Exception as e:
        print(f"  [ERROR] fetch failed '{keyword}': {e}")
        return []


def build_entry(raw: dict, hosted_image: str, expires_at_iso: str) -> dict:
    product_id = str(raw.get("product_id", ""))
    title = raw.get("product_title", "")
    discount_pct = _parse_int(str(raw.get("discount", "0")).strip("%"))
    rating_raw = _parse_float(str(raw.get("evaluate_rate", "0")).strip("%"))
    rating = round(rating_raw / 20.0, 1) if rating_raw else None
    return {
        "product_id": product_id,
        "title": title,
        "slug": slugify(title),
        "price": raw.get("target_sale_price"),
        "original_price": raw.get("target_original_price"),
        "discount_pct": discount_pct,
        "affiliate_url": raw.get("product_detail_url", ""),
        "image_url": hosted_image,
        "rating": rating,
        "reviews_count": _parse_int(raw.get("lastest_volume", 0)),
        "expires_at": expires_at_iso,
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not APP_KEY or not APP_SECRET:
        raise SystemExit("[ERROR] ALIEXPRESS_APP_KEY / ALIEXPRESS_APP_SECRET mancanti in .env")

    seen_ids = set()
    pool = []

    for kw in KEYWORDS:
        print(f"  keyword: {kw}")
        raw_list = fetch_hot_products(kw)
        for raw in raw_list:
            pid = str(raw.get("product_id", ""))
            if not pid or pid in seen_ids:
                continue
            title = raw.get("product_title", "")
            if not title or is_blacklisted(title):
                continue
            price = _parse_float(raw.get("target_sale_price") or raw.get("sale_price", "0"))
            if price <= 0 or price > MAX_PRICE_USD:
                continue
            discount_pct = _parse_int(str(raw.get("discount", "0")).strip("%"))
            if discount_pct < MIN_DISCOUNT_PCT:
                continue
            image_url = raw.get("product_main_image_url", "")
            if not image_url or "placeholder" in image_url.lower():
                continue
            seen_ids.add(pid)
            pool.append(raw)
        time.sleep(0.3)

    pool.sort(key=lambda r: _parse_int(str(r.get("discount", "0")).strip("%")), reverse=True)
    pool = pool[:TOP_N]

    expires_ts = int(time.time()) + EXPIRES_IN_SECONDS
    expires_at_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(expires_ts))

    products = []
    for raw in pool:
        pid = str(raw.get("product_id", ""))
        image_url = raw.get("product_main_image_url", "")
        hosted = upload_image(image_url, pid) if image_url else ""
        products.append(build_entry(raw, hosted, expires_at_iso))
        time.sleep(0.2)

    output = {
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "expires_at": expires_at_iso,
        "products": products,
    }
    out_path = OUTPUT_DIR / "en.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  -> {len(products)} flash deals -> {out_path}")


if __name__ == "__main__":
    main()
