"""
Fetch prodotti con coupon/discount alto da AliExpress Affiliate API.
Output: _data/coupons/en.json. Filtra prodotti con discount_pct > 30.
"""
import hashlib
import hmac
import json
import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "_data" / "coupons"

APP_KEY = os.getenv("ALIEXPRESS_APP_KEY", "")
APP_SECRET = os.getenv("ALIEXPRESS_APP_SECRET", "")
TRACKING_ID = os.getenv("ALIEXPRESS_TRACKING_ID", "")
API_URL = "https://api-sg.aliexpress.com/sync"

KEYWORD = "coupon discount"
MIN_DISCOUNT_PCT = 30


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


def fetch_hot_products(keyword: str, page_size: int = 40) -> list:
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
        print(f"  [ERROR] fetch failed: {e}")
        return []


def build_entry(raw: dict) -> dict:
    title = raw.get("product_title", "")

    discount_str = raw.get("discount", "0%")
    try:
        discount_pct = int(str(discount_str).strip("%"))
    except (ValueError, AttributeError):
        discount_pct = 0

    return {
        "product_id": str(raw.get("product_id", "")),
        "title": title,
        "slug": slugify(title),
        "price": raw.get("target_sale_price"),
        "original_price": raw.get("target_original_price"),
        "discount_pct": discount_pct,
        "affiliate_url": raw.get("product_detail_url", ""),
        "image_url": raw.get("product_main_image_url", ""),
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not APP_KEY or not APP_SECRET:
        raise SystemExit("[ERROR] ALIEXPRESS_APP_KEY / ALIEXPRESS_APP_SECRET mancanti in .env")

    print(f"Fetching coupons (keyword='{KEYWORD}')...")
    raw_list = fetch_hot_products(KEYWORD)

    entries = []
    for raw in raw_list:
        entry = build_entry(raw)
        if entry["discount_pct"] > MIN_DISCOUNT_PCT:
            entries.append(entry)

    entries.sort(key=lambda e: e["discount_pct"], reverse=True)

    output = {
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "min_discount_pct": MIN_DISCOUNT_PCT,
        "products": entries,
    }
    out_path = OUTPUT_DIR / "en.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  -> {len(entries)} coupons -> {out_path}")


if __name__ == "__main__":
    main()
