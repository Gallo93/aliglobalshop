"""
IndexNow ping for AliGlobalShop.

Reads the built sitemap.xml, extracts every <loc> URL, and submits them in one
batch to the IndexNow endpoint so Bing/Yandex re-crawl new and updated pages.
The IndexNow key lives in _data/config.json (indexnow_key) and is hosted
publicly at https://<host>/<key>.txt (written by build.py).

Designed to never break the deploy: if the sitemap is missing, the key is not
configured, or the request fails, it logs and exits 0.
"""
import json
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).parent.parent
CONFIG_PATH = BASE_DIR / "_data" / "config.json"
SITEMAP_PATH = BASE_DIR / "sitemap.xml"
ENDPOINT = "https://api.indexnow.org/indexnow"
MAX_URLS = 10000


def load_config() -> dict:
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"[indexnow] cannot read config: {exc}")
        return {}


def extract_urls(sitemap_path: Path) -> list:
    if not sitemap_path.exists():
        print(f"[indexnow] sitemap not found at {sitemap_path}, nothing to submit")
        return []
    try:
        tree = ET.parse(sitemap_path)
    except Exception as exc:
        print(f"[indexnow] cannot parse sitemap: {exc}")
        return []
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [el.text.strip() for el in tree.findall(".//sm:loc", ns) if el.text]
    if not locs:
        # Fallback for sitemaps without the default namespace.
        locs = [el.text.strip() for el in tree.iter() if el.tag.endswith("loc") and el.text]
    return locs[:MAX_URLS]


def submit(host: str, key: str, urls: list) -> None:
    payload = {
        "host": host,
        "key": key,
        "keyLocation": f"https://{host}/{key}.txt",
        "urlList": urls,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            if status in (200, 202):
                print(f"[indexnow] OK ({status}): submitted {len(urls)} URLs")
            else:
                print(f"[indexnow] unexpected status {status} for {len(urls)} URLs")
    except Exception as exc:
        print(f"[indexnow] submit failed: {exc}")


def main() -> None:
    config = load_config()
    key = config.get("indexnow_key", "")
    if not key:
        print("[indexnow] no indexnow_key in config, skipping")
        return
    site_url = config.get("site_url", "https://aliglobalshop.net").rstrip("/")
    host = urlparse(site_url).netloc or "aliglobalshop.net"
    urls = extract_urls(SITEMAP_PATH)
    if not urls:
        print("[indexnow] no URLs to submit, exiting cleanly")
        return
    submit(host, key, urls)


if __name__ == "__main__":
    main()
