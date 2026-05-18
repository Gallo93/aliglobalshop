"""
Ricarica prodotti esistenti in _data/products/en/*.json e aggiorna i prezzi
via aliexpress.affiliate.productdetail.get. Notifica Resend su price drop > 10%.
"""
import hashlib
import hmac
import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
PRODUCTS_DIR = BASE_DIR / "_data" / "products" / "en"

APP_KEY = os.getenv("ALIEXPRESS_APP_KEY", "")
APP_SECRET = os.getenv("ALIEXPRESS_APP_SECRET", "")
TRACKING_ID = os.getenv("ALIEXPRESS_TRACKING_ID", "")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM = os.getenv("RESEND_FROM", "alerts@aliglobalshop.com")
RESEND_TO = os.getenv("RESEND_TO", "")

API_URL = "https://api-sg.aliexpress.com/sync"
PRICE_DROP_THRESHOLD = 0.10
BATCH_SIZE = 20
SLEEP_BETWEEN_CALLS = 0.3


def _sign(params: dict) -> str:
    sorted_pairs = sorted(params.items())
    sign_str = "".join(f"{k}{v}" for k, v in sorted_pairs)
    return hmac.new(APP_SECRET.encode("utf-8"), sign_str.encode("utf-8"), hashlib.sha256).hexdigest().upper()


def _to_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_details(product_ids: list[str]) -> dict[str, dict]:
    if not product_ids:
        return {}

    params = {
        "app_key": APP_KEY,
        "format": "json",
        "method": "aliexpress.affiliate.productdetail.get",
        "product_ids": ",".join(product_ids),
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
            data.get("aliexpress_affiliate_productdetail_get_response", {})
            .get("resp_result", {})
        )
        if result.get("resp_code") != 200:
            print(f"  [WARN] API error {result.get('resp_code')}: {result.get('resp_msg')}")
            return {}
        products = result.get("result", {}).get("products", {}).get("product", [])
        return {str(p.get("product_id")): p for p in products}
    except Exception as e:
        print(f"  [ERROR] details fetch failed: {e}")
        return {}


def send_price_drop_alert(product: dict, old_price: float, new_price: float) -> None:
    if not RESEND_API_KEY or not RESEND_TO:
        return
    drop_pct = round((1 - new_price / old_price) * 100, 1)
    subject = f"Price drop: {product.get('title', '')[:60]} (-{drop_pct}%)"
    html = (
        f"<h2>Price drop alert</h2>"
        f"<p><strong>{product.get('title', '')}</strong></p>"
        f"<p>Old: ${old_price} -> New: ${new_price} ({drop_pct}% off)</p>"
        f"<p><a href=\"{product.get('affiliate_url', '')}\">Buy now</a></p>"
    )
    try:
        requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"from": RESEND_FROM, "to": [RESEND_TO], "subject": subject, "html": html},
            timeout=15,
        )
    except Exception as e:
        print(f"  [WARN] Resend alert failed: {e}")


def update_file(json_file: Path) -> int:
    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)

    products = data.get("products", []) if isinstance(data, dict) else data
    if not products:
        return 0

    updated_count = 0
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    for i in range(0, len(products), BATCH_SIZE):
        batch = products[i : i + BATCH_SIZE]
        ids = [str(p.get("product_id")) for p in batch if p.get("product_id")]
        details = fetch_details(ids)

        for product in batch:
            pid = str(product.get("product_id", ""))
            detail = details.get(pid)
            if not detail:
                continue

            new_price = detail.get("target_sale_price")
            if new_price is None:
                continue

            old_price_f = _to_float(product.get("price"))
            new_price_f = _to_float(new_price)

            product["price"] = new_price
            product["original_price"] = detail.get("target_original_price", product.get("original_price"))
            product["updated_at"] = now_iso
            updated_count += 1

            if (
                old_price_f is not None
                and new_price_f is not None
                and new_price_f < old_price_f * (1 - PRICE_DROP_THRESHOLD)
            ):
                send_price_drop_alert(product, old_price_f, new_price_f)

        time.sleep(SLEEP_BETWEEN_CALLS)

    if isinstance(data, dict):
        data["updated_at"] = now_iso
        data["products"] = products
    else:
        data = products

    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return updated_count


def main():
    if not APP_KEY or not APP_SECRET:
        raise SystemExit("[ERROR] ALIEXPRESS_APP_KEY / ALIEXPRESS_APP_SECRET mancanti in .env")

    if not PRODUCTS_DIR.exists():
        print(f"[INFO] {PRODUCTS_DIR} non esiste, nessun prodotto da aggiornare.")
        return

    total = 0
    for json_file in sorted(PRODUCTS_DIR.glob("*.json")):
        print(f"Updating {json_file.name}...")
        count = update_file(json_file)
        total += count
        print(f"  -> {count} prodotti aggiornati")

    print(f"Totale prodotti aggiornati: {total}")


if __name__ == "__main__":
    main()
