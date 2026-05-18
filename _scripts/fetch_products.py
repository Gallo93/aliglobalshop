"""
Fetch prodotti da AliExpress Affiliate API → upload immagini su Cloudinary → salva JSON
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
    "electronics": "electronics",
    "smart-home": "smart home",
    "sport": "sports outdoor",
    "gadgets": "gadgets",
}


def _sign(params: dict) -> str:
    # method included in params, sign excluded - no prefix
    sorted_pairs = sorted(params.items())
    sign_str = "".join(f"{k}{v}" for k, v in sorted_pairs)
    return hmac.new(APP_SECRET.encode("utf-8"), sign_str.encode("utf-8"), hashlib.sha256).hexdigest().upper()


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.ASCII)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:60]


def upload_image(image_url: str, product_id: str) -> str:
    try:
        result = cloudinary.uploader.upload(
            image_url,
            public_id=f"products/{product_id}",
            format="webp",
            overwrite=False,
            resource_type="image",
        )
        return result["secure_url"]
    except Exception as e:
        print(f"  [WARN] image upload failed {product_id}: {e}")
        return image_url


def fetch_products(keyword: str, page_size: int = 20) -> list:
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
        print(f"  [ERROR] fetch failed for '{keyword}': {e}")
        return []


def build_product(raw: dict, niche: str, hosted_image: str) -> dict:
    product_id = str(raw.get("product_id", ""))
    title = raw.get("product_title", "")

    discount_str = raw.get("discount", "0%")
    try:
        discount_pct = int(str(discount_str).strip("%"))
    except (ValueError, AttributeError):
        discount_pct = 0

    rating_str = raw.get("evaluate_rate", "0%")
    try:
        rating = round(float(str(rating_str).strip("%")) / 20, 1)
    except (ValueError, AttributeError):
        rating = None

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "product_id": product_id,
        "title": title,
        "slug": slugify(title),
        "price": raw.get("target_sale_price"),
        "original_price": raw.get("target_original_price"),
        "discount_pct": discount_pct,
        "affiliate_url": raw.get("product_detail_url", ""),
        "image_url": hosted_image,
        "category": niche,
        "rating": rating,
        "reviews_count": raw.get("lastest_volume"),
        "fetched_at": now,
        "updated_at": now,
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not APP_KEY or not APP_SECRET:
        raise SystemExit("[ERROR] ALIEXPRESS_APP_KEY / ALIEXPRESS_APP_SECRET mancanti in .env")

    for niche, keyword in NICHES.items():
        print(f"Fetching '{keyword}'...")
        raw_list = fetch_products(keyword)
        products = []
        for raw in raw_list:
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


if __name__ == "__main__":
    main()
