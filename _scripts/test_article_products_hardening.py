"""Test deterministico (no API, no rete) dei predicati di hardening degli
article-products in fetch_products.py: _is_medical_industrial, _article_price_ok
e il filtro combinato (stesse condizioni della comprehension di
fetch_article_products, senza chiamare la funzione intera che fa API+Cloudinary).

Eseguibile a mano (`python _scripts/test_article_products_hardening.py`) o via
pytest. Esce con codice != 0 al primo fallimento.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fetch_products as fp  # noqa: E402

# --- _is_medical_industrial --------------------------------------------------
MEDICAL_TRUE = [
    "ChoiceMMed Portable Finger Pulse Oximeter Blood Oxygen",  # pulse oximeter
    "Adult NIBP Cuff Reusable Digital Monitor Blood Pressure",  # nibp
    "Aicare Fingertip Pulse Oximeter SpO2",                    # pulse oximeter
    "Safewill Argon Gas Monitor Detector",                     # gas/argon
    "SEETEC 7 inch Carry-on Broadcast Monitor SDI",            # broadcast
    "Sinocare Safe AQ Glucometer Blood Glucose Test Kit",      # glucometer
]
MEDICAL_FALSE = [
    "15.6 inch Portable Monitor IPS 1080p USB-C HDMI Laptop Screen",
    "Gaming Mechanical Keyboard RGB Hot Swap",
    "Wireless Earbuds Bluetooth 5.3 Noise Cancelling",
    # GUARDIA anti-regressione: i wearable legittimi stampano queste feature
    # cliniche nel titolo e NON devono essere esclusi (topic fitness tracker /
    # smartwatch del calendario).
    "Smart Watch Men Heart Rate Blood Pressure Blood Oxygen SpO2 Fitness Tracker",
    "D18 Smartwatch Blood Glucose Heart Rate Fitness Tracker",
]

# --- _article_price_ok -------------------------------------------------------
PRICE_TRUE = [
    {"target_sale_price": "89.90"},
    {"target_sale_price": "299.99"},
    {"sale_price": "45.00"},
]
PRICE_FALSE = [
    {"target_sale_price": "4373.31"},   # oltre il tetto
    {"target_sale_price": "300.01"},    # appena oltre
    {"sale_price": "0"},                # zero
    {},                                  # prezzo assente
    {"target_sale_price": "abc"},       # non parsabile
]


def _passes_combined_filter(r: dict, topic_pattern, accessory_pattern) -> bool:
    """Replica esatta delle condizioni della comprehension `relevant` di
    fetch_article_products (cosi il test segue il codice reale)."""
    title = r.get("product_title", "")
    return (
        not fp.is_blacklisted(title)
        and not fp._is_accessory(title)
        and not fp._is_theme_accessory(title, accessory_pattern)
        and not fp._is_offtopic(title)
        and not fp._is_medical_industrial(title)
        and fp._article_price_ok(r)
        and fp._is_relevant(title, topic_pattern)
    )


def main() -> int:
    failures = []

    for t in MEDICAL_TRUE:
        if not fp._is_medical_industrial(t):
            failures.append(f"_is_medical_industrial deve essere True: {t!r}")
        else:
            print(f"[ok] medical/industrial True: {t!r}")
    for t in MEDICAL_FALSE:
        if fp._is_medical_industrial(t):
            failures.append(f"_is_medical_industrial deve essere False: {t!r}")
        else:
            print(f"[ok] medical/industrial False: {t!r}")

    for raw in PRICE_TRUE:
        if not fp._article_price_ok(raw):
            failures.append(f"_article_price_ok deve essere True: {raw!r}")
        else:
            print(f"[ok] price ok True: {raw!r}")
    for raw in PRICE_FALSE:
        if fp._article_price_ok(raw):
            failures.append(f"_article_price_ok deve essere False: {raw!r}")
        else:
            print(f"[ok] price ok False: {raw!r}")

    # --- filtro combinato sul caso reale "portable monitor" -----------------
    # search kw pulita per il topic monitor.
    clean_kw = fp._clean_search_kw("how to choose a portable monitor")
    topic_pattern = fp._resolve_topic_pattern(
        "how to choose a portable monitor portable monitor", clean_kw)
    accessory_pattern = fp._build_theme_accessory_pattern(clean_kw)

    # 4 medical/gas/broadcast + 2 SEETEC pro-prezzo + 1 monitor consumer valido.
    raw_monitor_case = [
        {"product_id": "1", "product_title": "ChoiceMMed Finger Pulse Oximeter Blood Oxygen Monitor",
         "target_sale_price": "12.50"},
        {"product_id": "2", "product_title": "Adult NIBP Blood Pressure Monitor Digital",
         "target_sale_price": "39.00"},
        {"product_id": "3", "product_title": "Safewill Argon Gas Monitor Detector",
         "target_sale_price": "88.00"},
        {"product_id": "4", "product_title": "Aicare Fingertip Pulse Oximeter SpO2",
         "target_sale_price": "9.90"},
        {"product_id": "5", "product_title": "SEETEC 21.5 inch Broadcast Monitor SDI 3G",
         "target_sale_price": "1658.00"},
        {"product_id": "6", "product_title": "SEETEC 28 inch 4K Broadcast Production Monitor",
         "target_sale_price": "4373.31"},
        {"product_id": "7", "product_title": "15.6 inch Portable Monitor IPS 1080p USB-C HDMI Screen",
         "target_sale_price": "95.00"},
    ]
    survivors = [
        r for r in raw_monitor_case
        if _passes_combined_filter(r, topic_pattern, accessory_pattern)
    ]
    survivor_ids = {r["product_id"] for r in survivors}
    # Tutti i medical/gas e i 2 SEETEC pro-prezzo devono cadere; resta solo il 7.
    if survivor_ids != {"7"}:
        failures.append(
            f"filtro combinato: sopravvissuti {sorted(survivor_ids)}, atteso {{'7'}}")
    else:
        print("[ok] filtro combinato caso monitor: resta solo il consumer (id 7)")

    print()
    if failures:
        print(f"FALLITI {len(failures)} controlli:")
        for f in failures:
            print("  -", f)
        return 1
    print("TUTTI I CONTROLLI PASSATI")
    return 0


def test_article_products_hardening():
    """Entry-point pytest."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
