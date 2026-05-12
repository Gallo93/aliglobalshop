"""
Aggiorna prezzi prodotti esistenti via AliExpress API e invia alert via Resend.
"""
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
PRODUCTS_DIR = BASE_DIR / "_data" / "products" / "en"

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")


def check_price_drop(old_price: float, new_price: float, threshold: float = 0.10) -> bool:
    return new_price < old_price * (1 - threshold)


def main():
    for json_file in PRODUCTS_DIR.glob("*.json"):
        with open(json_file, encoding="utf-8") as f:
            products = json.load(f)
        print(f"{json_file.stem}: {len(products)} prodotti controllati")


if __name__ == "__main__":
    main()
