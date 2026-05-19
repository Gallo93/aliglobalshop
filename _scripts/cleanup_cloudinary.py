"""
Weekly Cloudinary cleanup: deletes assets in products/, flash-sale/, coupons/
that are no longer referenced in _data/ JSON files.
"""
import json
import os
from pathlib import Path

import cloudinary
import cloudinary.api
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "_data"

FOLDERS = ["products", "flash-sale", "coupons"]

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME", ""),
    api_key=os.getenv("CLOUDINARY_API_KEY", ""),
    api_secret=os.getenv("CLOUDINARY_API_SECRET", ""),
)


def collect_active_ids() -> set:
    active = set()

    products_dir = DATA_DIR / "products" / "en"
    if products_dir.exists():
        for f in products_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                for p in data.get("products", []):
                    pid = str(p.get("product_id", ""))
                    if pid:
                        active.add(pid)
            except Exception as e:
                print(f"[warn] cannot parse {f}: {e}")

    flash_path = DATA_DIR / "flash-sale" / "en.json"
    if flash_path.exists():
        try:
            data = json.loads(flash_path.read_text(encoding="utf-8"))
            for p in data.get("products", []):
                pid = str(p.get("product_id", ""))
                if pid:
                    active.add(pid)
        except Exception as e:
            print(f"[warn] cannot parse flash-sale: {e}")

    coupons_path = DATA_DIR / "coupons" / "en.json"
    if coupons_path.exists():
        try:
            data = json.loads(coupons_path.read_text(encoding="utf-8"))
            for p in data.get("products", []):
                pid = str(p.get("product_id", ""))
                if pid:
                    active.add(pid)
        except Exception as e:
            print(f"[warn] cannot parse coupons: {e}")

    return active


def list_cloudinary_assets(folder: str) -> list:
    assets = []
    next_cursor = None
    while True:
        kwargs = {
            "type": "upload",
            "prefix": f"{folder}/",
            "max_results": 500,
        }
        if next_cursor:
            kwargs["next_cursor"] = next_cursor
        try:
            result = cloudinary.api.resources(**kwargs)
            for r in result.get("resources", []):
                assets.append(r["public_id"])
            next_cursor = result.get("next_cursor")
            if not next_cursor:
                break
        except Exception as e:
            print(f"[error] listing {folder}: {e}")
            break
    return assets


def main():
    if not os.getenv("CLOUDINARY_API_KEY"):
        raise SystemExit("[ERROR] CLOUDINARY_API_KEY mancante in .env")

    print("Collecting active product IDs...")
    active_ids = collect_active_ids()
    print(f"  Active product IDs: {len(active_ids)}")

    total_deleted = 0
    total_kept = 0

    for folder in FOLDERS:
        print(f"\nChecking folder '{folder}'...")
        assets = list_cloudinary_assets(folder)
        print(f"  Found {len(assets)} assets")

        to_delete = []
        for public_id in assets:
            pid = public_id.split("/", 1)[-1]
            if pid not in active_ids:
                to_delete.append(public_id)

        print(f"  To delete: {len(to_delete)}, to keep: {len(assets) - len(to_delete)}")
        total_kept += len(assets) - len(to_delete)

        for i in range(0, len(to_delete), 100):
            batch = to_delete[i:i + 100]
            try:
                result = cloudinary.api.delete_resources(batch)
                deleted_count = sum(1 for v in result.get("deleted", {}).values() if v == "deleted")
                total_deleted += deleted_count
                print(f"  Deleted batch {i//100 + 1}: {deleted_count}/{len(batch)}")
            except Exception as e:
                print(f"  [error] delete batch failed: {e}")

    print(f"\nDone. Deleted: {total_deleted}, kept: {total_kept}")


if __name__ == "__main__":
    main()
