"""
Test offline (stdlib, niente rete/API) per due filtri degli article-products in
fetch_products.py:
  1. pavimento di prezzo ARTICLE_MIN_PRICE_USD in _article_price_ok
  2. termine accessorio 'connector' in _ACCESSORY_PATTERN (_is_accessory)

Diagnosi: l'articolo speaker mostrava un accessorio "... USB Female Connector"
a $0.59 (ricambio, non uno speaker) perche' passava i filtri: il titolo contiene
"Speaker" e non c'era ne' un prezzo minimo ne' il termine 'connector' tra gli
accessori. Entrambi i controlli lo scartano ora.

Uso: python test_article_min_price.py  (exit 0 = OK, 1 = fallito)
"""
import sys

from fetch_products import _article_price_ok, _is_accessory


def main() -> int:
    # 1. Sotto il minimo: il connettore a $0.59 non passa.
    assert _article_price_ok({"target_sale_price": "0.59"}) is False

    # 2. Speaker veri nella fascia valida (<=300).
    assert _article_price_ok({"target_sale_price": "5.47"}) is True
    assert _article_price_ok({"target_sale_price": "19.84"}) is True
    assert _article_price_ok({"target_sale_price": "30.35"}) is True
    assert _article_price_ok({"target_sale_price": "181.87"}) is True

    # 3. Sopra il massimo.
    assert _article_price_ok({"target_sale_price": "350"}) is False

    # 4. Bordi del minimo.
    assert _article_price_ok({"target_sale_price": "3"}) is True
    assert _article_price_ok({"target_sale_price": "2.99"}) is False

    # 5. Nuovo termine accessorio 'connector'.
    assert _is_accessory(
        "2-10pcs For JBL CHARGE 4 5 Bluetooth Audio Wireless Portable Small "
        "Speaker Power Charging Port Type-C 16p USB Female Connector"
    ) is True

    # 6. Non-regressione: speaker veri NON sono accessori.
    assert _is_accessory(
        "Portable Wireless Bluetooth Speaker Bass Column Outdoor USB"
    ) is False
    assert _is_accessory(
        "EWA A117 Magsafe Wireless Bluetooth Speaker"
    ) is False

    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
