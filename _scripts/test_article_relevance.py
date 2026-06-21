"""Test deterministico (no API, no rete) della pertinenza article-products.

Verifica due meccanismi introdotti per evitare prodotti fuori tema in fondo
agli articoli blog:

  fetch_products.py
    - `_resolve_topic_pattern` + `_dynamic_topic_pattern`: per OGNI topic
      (anche fuori dalla whitelist hardcoded) costruisce un pattern-tema sul
      sostantivo-testa, e `_is_relevant`/`_is_offtopic` accettano il prodotto
      giusto e scartano power bank / LED strip / accessori.
    - nessuna regressione sui temi gia coperti (earbuds, vacuum, smartwatch,
      home gym).

  build.py
    - `related_products_section_html`: la rete di sicurezza sul fallback di
      categoria scarta gli off-topic e, se restano <2 pertinenti, NON mostra
      alcun blocco prodotti (stringa vuota).

Eseguibile a mano (`python _scripts/test_article_relevance.py`) o via pytest.
Esce con codice != 0 al primo fallimento.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fetch_products import (  # noqa: E402
    _clean_search_kw,
    _is_offtopic,
    _is_relevant,
    _resolve_topic_pattern,
)
import build  # noqa: E402


def _topic_pattern_for(title: str, primary_kw: str):
    combined = f"{title} {primary_kw}"
    clean_kw = _clean_search_kw(primary_kw) or _clean_search_kw(title)
    return _resolve_topic_pattern(combined, clean_kw)


# (1) fetch_products: pertinenza per articolo.
# Ogni voce: (title, primary_kw, [titoli che DEVONO passare], [titoli da SCARTARE]).
ARTICLE_CASES = [
    (
        "Best AliExpress Gaming Mouse 2026",
        "aliexpress gaming mouse",
        [
            "Wireless Gaming Mouse 26000DPI RGB Rechargeable Ergonomic",
            "ATTACK SHARK X3 Bluetooth Gaming Mouse Lightweight",
        ],
        [
            "QOOVI PD 100W Power Bank 20000mAh Fast Charging",
            "LED Strip Light RGB 5050 Bluetooth App Control",
        ],
    ),
    (
        "AliExpress Mechanical Keyboard Picks 2026",
        "aliexpress mechanical keyboard",
        [
            "Wireless Mechanical Keyboard 75% Hot Swappable RGB Gasket",
        ],
        [
            "20000mAh Power Bank Portable Charger Dual USB",
        ],
    ),
    (
        "Cheap AliExpress Drone Under $100 (2026)",
        "aliexpress cheap drone",
        [
            "4K HD Camera Drone GPS Foldable Quadcopter Brushless",
        ],
        [
            "Phone Holder Car Mount Magnetic Adapter",
        ],
    ),
    # --- temi gia coperti dalla whitelist: nessuna regressione ---
    (
        "Best AliExpress Earbuds 2026",
        "aliexpress wireless earbuds",
        [
            "TWS Wireless Earbuds Bluetooth 5.3 Noise Cancelling",
        ],
        [
            "Power Bank 30000mAh Fast Charging",
        ],
    ),
    (
        "AliExpress Robot Vacuum Reviews 2026",
        "aliexpress robot vacuum",
        [
            "Robot Vacuum Cleaner Wet Dry Mop Self Charging",
        ],
        [
            "USB Power Bank Slim 10000mAh",
        ],
    ),
    (
        "AliExpress Smartwatch Guide 2026",
        "aliexpress smartwatch",
        [
            "Smart Watch Men Bluetooth Call Heart Rate AMOLED",
        ],
        [
            "Wall Adapter Charger 65W GaN",
        ],
    ),
    (
        "AliExpress Home Gym Equipment 2026",
        "aliexpress home gym equipment",
        [
            "Adjustable Dumbbell Set Home Gym Equipment 24kg",
        ],
        [
            "Power Bank Solar 20000mAh Waterproof",
        ],
    ),
]


class _FakeT(dict):
    """T minimale per related_products_section_html (solo .get usati)."""


def _build_offtopic_case():
    """(2) rete di sicurezza build.py: categoria mista, topic 'mouse'.
    Deve scartare gli off-topic e, se <2 pertinenti, restituire stringa vuota."""
    products_by_cat = {
        "electronics": {
            "products": [
                {"title": "QOOVI Power Bank 20000mAh Fast Charging", "price": 19.9},
                {"title": "LED Strip Light RGB Bluetooth 5m", "price": 9.9},
                {"title": "USB Wall Adapter 65W GaN Charger", "price": 14.9},
            ]
        }
    }
    return products_by_cat


def main() -> int:
    failures = []

    # (1) fetch_products: pertinenza per articolo
    for title, kw, must_pass, must_drop in ARTICLE_CASES:
        pattern = _topic_pattern_for(title, kw)
        if pattern is None:
            failures.append(f"[1] nessun pattern-tema per {kw!r}")
            continue
        for prod_title in must_pass:
            ok = _is_relevant(prod_title, pattern) and not _is_offtopic(prod_title)
            if not ok:
                failures.append(
                    f"[1] {kw!r}: '{prod_title}' DOVEVA passare "
                    f"(relevant={_is_relevant(prod_title, pattern)}, "
                    f"offtopic={_is_offtopic(prod_title)})"
                )
            else:
                print(f"[1] OK {kw:32s} pass  <- {prod_title[:45]!r}")
        for prod_title in must_drop:
            dropped = _is_offtopic(prod_title) or not _is_relevant(prod_title, pattern)
            if not dropped:
                failures.append(
                    f"[1] {kw!r}: '{prod_title}' DOVEVA essere scartato"
                )
            else:
                print(f"[1] OK {kw:32s} drop  <- {prod_title[:45]!r}")

    # (2) rete di sicurezza build.py sul fallback di categoria
    products_by_cat = _build_offtopic_case()
    T = _FakeT()
    # topic_kws = ['mouse'] (sostantivo-testa di 'gaming mouse'): nessun prodotto
    # di categoria e' un mouse e i power bank/LED/adapter sono off-topic ->
    # blocco prodotti vuoto (meglio nessuno che sbagliato).
    out = build.related_products_section_html(
        "electronics", products_by_cat, "https://example.com", "en", T,
        limit=4, topic_kws=["mouse"],
    )
    if out != "":
        failures.append(f"[2] fallback DOVEVA essere vuoto, invece: {out[:80]!r}")
    else:
        print("[2] OK fallback vuoto su categoria mista off-topic (topic 'mouse')")

    # (2b) i prodotti palesemente off-topic non passano nemmeno senza topic_kws
    out2 = build.related_products_section_html(
        "electronics", products_by_cat, "https://example.com", "en", T,
        limit=4, topic_kws=None,
    )
    if "Power Bank" in out2 or "power bank" in out2.lower():
        failures.append("[2b] il power bank off-topic e' finito nel fallback")
    else:
        print("[2b] OK nessun power bank nel fallback (off-topic guard)")

    print()
    if failures:
        print(f"FALLITI {len(failures)} controlli:")
        for f in failures:
            print("  -", f)
        return 1
    print("TUTTI I CONTROLLI PASSATI")
    return 0


def test_article_relevance():
    """Entry-point pytest."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
