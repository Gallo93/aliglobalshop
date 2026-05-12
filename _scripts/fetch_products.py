"""
Fetch prodotti da AliExpress Affiliate API e salva JSON in _data/products/en/<niche>.json
"""
import json
import os
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "_data" / "products" / "en"

ALIEXPRESS_APP_KEY = os.getenv("ALIEXPRESS_APP_KEY", "")
ALIEXPRESS_APP_SECRET = os.getenv("ALIEXPRESS_APP_SECRET", "")
ALIEXPRESS_TRACKING_ID = os.getenv("ALIEXPRESS_TRACKING_ID", "")

NICHES = ["electronics", "smart-home", "sport", "gadgets"]


def fetch_niche(niche: str) -> list[dict]:
    # TODO: chiamata reale a portals.aliexpress.com
    return []


def main():
    for niche in NICHES:
        products = fetch_niche(niche)
        out_path = OUTPUT_DIR / f"{niche}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
        print(f"{niche}: {len(products)} prodotti salvati")
        time.sleep(1)


if __name__ == "__main__":
    main()
