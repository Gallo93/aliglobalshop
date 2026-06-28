"""Test deterministico (no API, no rete) dell'override `product_search` degli
article-products in fetch_products.py.

Copre:
- helper puro `_article_search_kw`: override presente -> override; assente o
  whitespace -> fallback;
- `fetch_article_products` con fetch_products/upload_image STUBBATI in una dir
  tmp: un articolo CON `product_search` -> l'API riceve la frase override; uno
  SENZA -> riceve la keyword derivata dal primary_keyword; e la PERTINENZA resta
  ancorata al topic reale (un monitor pertinente passa, gli earbuds off-topic no).

Eseguibile a mano o via pytest. Esce con codice != 0 al primo fallimento.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fetch_products as fp  # noqa: E402

OVERRIDE = "portable monitor usb c laptop"

# Prodotti raw che lo stub di fetch_products restituisce per OGNI chiamata:
# 2 monitor pertinenti a prezzo valido + 1 earbuds off-topic (non pertinente
# al topic "portable monitor").
_RAW = [
    {"product_id": "m1", "product_title": "15.6 inch Portable Monitor IPS USB-C HDMI",
     "target_sale_price": "95.00", "product_main_image_url": "http://x/1.jpg"},
    {"product_id": "m2", "product_title": "13.3 inch Portable Monitor 1080p Type-C",
     "target_sale_price": "120.00", "product_main_image_url": "http://x/2.jpg"},
    {"product_id": "e1", "product_title": "Wireless Earbuds Bluetooth 5.3 Noise Cancelling",
     "target_sale_price": "19.00", "product_main_image_url": "http://x/3.jpg"},
]


def _article(slug, **over):
    a = {
        "slug": slug,
        "primary_keyword": "portable monitor",
        "title": "Portable Monitor Buying Guide",
        "category": "electronics",
    }
    a.update(over)
    return a


def test_helper_pure():
    assert fp._article_search_kw(_article("s", product_search=OVERRIDE), "fallback") == OVERRIDE
    assert fp._article_search_kw(_article("s"), "fallback") == "fallback"
    # whitespace-only -> fallback
    assert fp._article_search_kw(_article("s", product_search="   "), "fallback") == "fallback"
    # product_search None esplicito -> fallback
    assert fp._article_search_kw(_article("s", product_search=None), "fallback") == "fallback"
    print("[ok] helper _article_search_kw: override / fallback / whitespace / None")


def test_fetch_article_products_override():
    tmp = Path(tempfile.mkdtemp(prefix="pso-test-"))
    blog_dir = tmp / "blog" / "en"
    out_dir = tmp / "products" / "en" / "_article"
    blog_dir.mkdir(parents=True)

    # File nominati cosi che 'a_' venga prima di 'b_' in sorted(): A=override, B=plain.
    (blog_dir / "a_override.json").write_text(
        json.dumps(_article("portable-monitor-override-2026", product_search=OVERRIDE),
                   ensure_ascii=False), encoding="utf-8")
    (blog_dir / "b_plain.json").write_text(
        json.dumps(_article("portable-monitor-guide-2026"), ensure_ascii=False),
        encoding="utf-8")

    calls = []
    saved_fetch = fp.fetch_products
    saved_upload = fp.upload_image
    fp.fetch_products = lambda keyword, page_size=30: (calls.append(keyword) or list(_RAW))
    fp.upload_image = lambda image_url, product_id: ""
    try:
        fp.fetch_article_products(blog_dir, out_dir)
    finally:
        fp.fetch_products = saved_fetch
        fp.upload_image = saved_upload

    # Keyword passate all'API, in ordine (A override, poi B fallback).
    assert calls == [OVERRIDE, "portable monitor"], \
        f"keyword API attese [override, 'portable monitor'], viste {calls}"

    # Pertinenza ancorata al topic reale: solo i 2 monitor sopravvivono, gli
    # earbuds off-topic vengono scartati. Vale per ENTRAMBI gli articoli.
    for slug in ("portable-monitor-override-2026", "portable-monitor-guide-2026"):
        data = json.loads((out_dir / f"{slug}.json").read_text(encoding="utf-8"))
        ids = {p["product_id"] for p in data["products"]}
        assert ids == {"m1", "m2"}, f"{slug}: prodotti {ids}, attesi {{m1, m2}} (no earbuds)"

    print("[ok] override: API riceve la query mirata, fallback derivato, "
          "earbuds off-topic scartati su entrambi")


_TESTS = [test_helper_pure, test_fetch_article_products_override]


def main() -> int:
    failures = []
    for t in _TESTS:
        try:
            t()
        except AssertionError as exc:
            failures.append(f"{t.__name__}: {exc}")
            print(f"[FAIL] {t.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{t.__name__}: {type(exc).__name__}: {exc}")
            print(f"[ERROR] {t.__name__}: {type(exc).__name__}: {exc}")
    print()
    if failures:
        print(f"FALLITI {len(failures)} test:")
        for f in failures:
            print("  -", f)
        return 1
    print(f"TUTTI I {len(_TESTS)} TEST PASSATI")
    return 0


if __name__ == "__main__":
    sys.exit(main())
