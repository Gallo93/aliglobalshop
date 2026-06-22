"""Test deterministico (no API, no rete) della pertinenza article-products.

Verifica i meccanismi introdotti per evitare prodotti fuori tema in fondo agli
articoli blog:

  fetch_products.py
    - `_resolve_topic_pattern` + `_dynamic_topic_pattern`: per OGNI topic
      (anche fuori dalla whitelist hardcoded) costruisce un pattern-tema sul
      sostantivo-testa, e `_is_relevant`/`_is_offtopic` accettano il prodotto
      giusto e scartano power bank / LED strip / accessori.
    - `_build_theme_accessory_pattern` + `_is_theme_accessory` (round 2/3):
      filtro CONDIZIONALE degli accessori-del-tema in DUE classi. HARD
      (pad/mat, keycaps, switch, stabilizer, wrist/palm rest): un device vero
      non li contiene mai -> match su TUTTO il titolo (i titoli AliExpress
      spingono il sostantivo oltre il 4o token). SOFT (band/strap/case/...):
      possono essere feature in coda di un device vero -> match solo sulla
      testa. Casi-tema che SONO l'accessorio (yoga mat, watch strap) NON
      vengono esclusi (protezione condizionale sul topic head-noun).
    - nessuna regressione sui temi gia coperti (earbuds, vacuum, smartwatch,
      home gym, lighting).

  build.py
    - `related_products_section_html`: la rete di sicurezza sul fallback di
      categoria scarta gli off-topic e gli accessori-del-tema (HARD/SOFT) e, se
      restano <2 pertinenti, NON mostra alcun blocco prodotti (stringa vuota).

Eseguibile a mano (`python _scripts/test_article_relevance.py`) o via pytest.
Esce con codice != 0 al primo fallimento.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fetch_products import (  # noqa: E402
    _build_theme_accessory_pattern,
    _clean_search_kw,
    _is_accessory,
    _is_offtopic,
    _is_relevant,
    _is_theme_accessory,
    _resolve_topic_pattern,
)
import build  # noqa: E402


def _topic_pattern_for(title: str, primary_kw: str):
    combined = f"{title} {primary_kw}"
    clean_kw = _clean_search_kw(primary_kw) or _clean_search_kw(title)
    return _resolve_topic_pattern(combined, clean_kw)


def _accessory_pattern_for(title: str, primary_kw: str):
    clean_kw = _clean_search_kw(primary_kw) or _clean_search_kw(title)
    return _build_theme_accessory_pattern(clean_kw)


# (1) fetch_products: pertinenza per articolo.
# Ogni voce: (title, primary_kw, [titoli che DEVONO passare], [titoli da SCARTARE]).
ARTICLE_CASES = [
    (
        "Best AliExpress Gaming Mouse 2026",
        "aliexpress gaming mouse",
        [
            "Wireless Gaming Mouse 26000DPI RGB Rechargeable Ergonomic",
            "ATTACK SHARK X3 Bluetooth Gaming Mouse Lightweight",
            # round 3: device veri con accessorio oltre il 4o token NON cadono
            "Wireless Gaming Mouse 26000DPI RGB",
            "Kensington Orbit 2.4G Wireless Trackball Mouse",
            "Cheerdots 2 Detachable Air Mouse Wireless Presenter",
        ],
        [
            "QOOVI PD 100W Power Bank 20000mAh Fast Charging",
            "LED Strip Light RGB 5050 Bluetooth App Control",
            # round 2: accessori-del-tema in testa
            "LED Mouse Pad RGB Large Gaming",
            "Gaming Mousepad XL Extended Desk",
            "Mouse Mat Desk Waterproof",
            # round 3: 'Pad'/'Mat' oltre il 4o token (HARD, su tutto il titolo)
            "Wholesale Custom XXL Extended Gaming Mouse Pad Anti-Slip Rubber",
            "Anime C-crayon Shin-chan Mouse Pad Gamer Keyboard Pad",
            "FIFA 2026 World Cup Football Large Mouse Pad Desk",
            "Large Size Leather Desk Pad Office Desk Mat Waterproof",
        ],
    ),
    (
        "AliExpress Mechanical Keyboard Picks 2026",
        "aliexpress mechanical keyboard",
        [
            "Wireless Mechanical Keyboard 75% Hot Swappable RGB Gasket",
            "Mechanical Keyboard 87 Keys RGB Hot-Swappable",
        ],
        [
            "20000mAh Power Bank Portable Charger Dual USB",
            # round 2: accessori-del-tema in testa
            "PBT Keycaps Set 104 Keys Double Shot",
            "Gateron Switches Linear 70pcs",
            # round 3: keycaps/switches oltre il 4o token (HARD)
            "Black and White Theme Double Shot Keyboard Keycaps PBT",
            "Gateron Milky Yellow Pro V3 Linear Switches 5pin",
            "NPKC Cherry Profile PBT Keycap Set Dye Sub",
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
    # --- REGRESSIONE CRITICA: il prodotto-tema E' l'accessorio (yoga mat) ---
    (
        "Best AliExpress Yoga Mat 2026",
        "aliexpress yoga mat",
        [
            "Non-Slip Yoga Mat 6mm Thick Exercise Fitness TPE",
        ],
        [
            "Power Bank 20000mAh Fast Charging",
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
            # device vero che cita 'band' come feature in coda: NON deve cadere
            "Smart Watch Men Bluetooth Call Heart Rate AMOLED Silicone Band",
        ],
        [
            "Wall Adapter Charger 65W GaN",
            # round 2: accessorio-del-tema (cinturino) che guida col nome
            "Watch Strap Silicone Band 22mm Quick Release",
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


def _build_accessory_fallback_case():
    """(3) rete di sicurezza build.py round 2: categoria con UN mouse vero +
    accessori-del-tema (mouse pad). Con topic 'mouse' gli accessori vanno
    scartati e, restando <2 mouse veri, il blocco deve risultare vuoto."""
    return {
        "electronics": {
            "products": [
                {"title": "Wireless Gaming Mouse 26000DPI RGB Ergonomic", "price": 19.9},
                {"title": "LED Mouse Pad RGB Large Gaming", "price": 8.9},
                {"title": "Gaming Mousepad XL Extended Desk", "price": 7.9},
            ]
        }
    }


def _build_accessory_fulltitle_case():
    """(3c) round 3: due mouse veri + accessori con 'Pad' OLTRE il 4o token.
    Gli accessori HARD vanno scartati anche se il sostantivo e' in coda; i due
    mouse veri restano -> il blocco si mostra e NON contiene 'pad'."""
    return {
        "electronics": {
            "products": [
                {"title": "Wholesale Custom XXL Extended Gaming Mouse Pad Anti-Slip", "price": 6.9},
                {"title": "FIFA 2026 World Cup Football Large Mouse Pad Desk", "price": 5.9},
                {"title": "Wireless Gaming Mouse 26000DPI RGB Ergonomic", "price": 19.9},
                {"title": "Kensington Orbit 2.4G Wireless Trackball Mouse", "price": 29.9},
            ]
        }
    }


def main() -> int:
    failures = []

    # (1) fetch_products: pertinenza + accessori-del-tema per articolo
    for title, kw, must_pass, must_drop in ARTICLE_CASES:
        pattern = _topic_pattern_for(title, kw)
        acc_pattern = _accessory_pattern_for(title, kw)
        if pattern is None:
            failures.append(f"[1] nessun pattern-tema per {kw!r}")
            continue
        for prod_title in must_pass:
            ok = (
                _is_relevant(prod_title, pattern)
                and not _is_offtopic(prod_title)
                and not _is_accessory(prod_title)
                and not _is_theme_accessory(prod_title, acc_pattern)
            )
            if not ok:
                failures.append(
                    f"[1] {kw!r}: '{prod_title}' DOVEVA passare "
                    f"(relevant={_is_relevant(prod_title, pattern)}, "
                    f"offtopic={_is_offtopic(prod_title)}, "
                    f"accessory={_is_accessory(prod_title)}, "
                    f"theme_acc={_is_theme_accessory(prod_title, acc_pattern)})"
                )
            else:
                print(f"[1] OK {kw:32s} pass  <- {prod_title[:45]!r}")
        for prod_title in must_drop:
            dropped = (
                _is_offtopic(prod_title)
                or _is_accessory(prod_title)
                or _is_theme_accessory(prod_title, acc_pattern)
                or not _is_relevant(prod_title, pattern)
            )
            if not dropped:
                failures.append(
                    f"[1] {kw!r}: '{prod_title}' DOVEVA essere scartato"
                )
            else:
                print(f"[1] OK {kw:32s} drop  <- {prod_title[:45]!r}")

    # (2) rete di sicurezza build.py sul fallback di categoria
    products_by_cat = _build_offtopic_case()
    T = _FakeT()
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

    # (3) rete di sicurezza build.py round 2: accessori-del-tema (mouse pad)
    acc_cat = _build_accessory_fallback_case()
    out3 = build.related_products_section_html(
        "electronics", acc_cat, "https://example.com", "en", T,
        limit=4, topic_kws=["mouse"],
    )
    if out3 != "":
        failures.append(
            f"[3] fallback DOVEVA essere vuoto (1 solo mouse vero), invece: {out3[:80]!r}"
        )
    elif "mousepad" in out3.lower() or "mouse pad" in out3.lower():
        failures.append("[3] un mouse pad e' finito nel fallback")
    else:
        print("[3] OK accessori-del-tema (mouse pad) esclusi dal fallback (topic 'mouse')")

    # (3b) topic CHE E' l'accessorio (yoga mat): lo yoga mat NON va escluso ->
    # con 2 yoga mat veri il blocco si mostra.
    yoga_cat = {
        "sport": {
            "products": [
                {"title": "Non-Slip Yoga Mat 6mm Thick TPE", "price": 15.9},
                {"title": "Eco Yoga Mat 8mm Extra Thick Exercise", "price": 18.9},
            ]
        }
    }
    out4 = build.related_products_section_html(
        "sport", yoga_cat, "https://example.com", "en", T,
        limit=4, topic_kws=["mat"],
    )
    if "Yoga Mat" not in out4:
        failures.append("[3b] gli yoga mat (prodotto-tema = accessorio) sono stati esclusi")
    else:
        print("[3b] OK yoga mat tenuti (topic 'mat' disattiva l'esclusione 'mat/pad')")

    # (3c) round 3: accessori con 'Pad'/'Mat' OLTRE il 4o token (HARD su tutto
    # il titolo). I due mouse veri restano -> blocco mostrato, senza 'pad'.
    fulltitle_cat = _build_accessory_fulltitle_case()
    out5 = build.related_products_section_html(
        "electronics", fulltitle_cat, "https://example.com", "en", T,
        limit=4, topic_kws=["mouse"],
    )
    if "pad" in out5.lower() or "mat" in out5.lower():
        failures.append(
            "[3c] un mouse pad/mat con sostantivo in coda e' finito nel fallback"
        )
    elif "Wireless Gaming Mouse" not in out5 or "Trackball Mouse" not in out5:
        failures.append(
            f"[3c] i mouse veri DOVEVANO restare, invece: {out5[:120]!r}"
        )
    else:
        print("[3c] OK accessori HARD (Pad/Mat oltre il 4o token) esclusi, mouse veri tenuti")

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
