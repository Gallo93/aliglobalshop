"""
Test offline (stdlib puro, no rete, no chiamate API) del fix "parole valuta
in _KW_STOPWORDS".

Bug: primary_keyword = "best bluetooth speaker under 30 dollars".
_clean_search_kw toglieva 'best'/'under'/'30' ma NON 'dollars' (non era
stopword) -> _dynamic_topic_pattern prendeva 'dollars' come sostantivo-testa
-> pattern \b(?:dollars?|speaker\s+dollars?)\b -> nessun titolo di speaker
Bluetooth contiene 'dollar' -> 0 prodotti pertinenti -> related vuota. Stessa
classe del bug 'pcs' (PR #43).

Fix: aggiunte al set _KW_STOPWORDS le parole valuta/prezzo (dollar/dollars/
usd/euro/eur/pound/gbp/buck/price/cost/money...), che sono modificatori di
budget e mai il sostantivo-testa di un prodotto.

Esce 0 se tutti gli assert passano, 1 altrimenti.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fetch_products import (  # noqa: E402
    _clean_search_kw,
    _dynamic_topic_pattern,
    _resolve_topic_pattern,
    _is_relevant,
)


def _matches(pattern, title: str) -> bool:
    """Wrapper leggibile: usa _is_relevant come lo usa fetch_article_products."""
    return _is_relevant(title, pattern)


def test_fix_speaker_under_30_dollars():
    """FIX: 'dollars' non deve piu' inquinare la keyword ne' l'head-noun; il
    pattern risolto deve matchare gli speaker veri e non un cavo USB."""
    primary = "best bluetooth speaker under 30 dollars"
    clean = _clean_search_kw(primary)

    # 'dollar'/'dollars' spariti dalla keyword pulita.
    assert "dollar" not in clean.split(), clean
    assert "dollars" not in clean.split(), clean
    # Resta il tema vero.
    assert "speaker" in clean.split(), clean

    # L'head-noun risolve su 'speaker': il pattern dinamico matcha lo speaker
    # ma NON un titolo che contiene solo 'dollar'.
    dyn = _dynamic_topic_pattern(clean)
    assert dyn is not None
    assert dyn.search("Portable Wireless Bluetooth Speaker Outdoor")
    assert not dyn.search("Cheap Gadget only 5 dollar clearance")

    # Pattern risolto end-to-end come in fetch_article_products.
    pattern = _resolve_topic_pattern(primary, clean)
    assert pattern is not None
    assert _matches(pattern, "Portable Wireless Bluetooth Speaker Outdoor")
    assert _matches(pattern, "TWS Mini Bluetooth Speaker")
    assert not _matches(pattern, "USB Cable 3m")
    print("  [OK] FIX speaker under 30 dollars -> head 'speaker'")


def test_regression_currency_other_niche():
    """REGRESSIONE valuta su altra nicchia: 'best fitness tracker under 30
    dollars' -> tema 'fitness tracker', matcha uno smartwatch/tracker vero e
    non e' contaminato da 'dollars'."""
    primary = "best fitness tracker under 30 dollars"
    clean = _clean_search_kw(primary)
    assert "dollar" not in clean.split() and "dollars" not in clean.split(), clean
    assert "tracker" in clean.split(), clean

    pattern = _resolve_topic_pattern(primary, clean)
    assert pattern is not None
    assert _matches(pattern, "Smart Watch Fitness Tracker Heart Rate")
    print("  [OK] regressione valuta fitness tracker")


def test_non_regression_mini_pc():
    """NON-REGRESSIONE mini-pc: 'pcs' NON e' tra le nuove stopword valuta e
    resta nella keyword; il pattern matcha ancora 'Mini PC'."""
    primary = "are cheap mini pcs worth it"
    clean = _clean_search_kw(primary)
    assert "pcs" in clean.split(), clean

    pattern = _resolve_topic_pattern(primary, clean)
    assert pattern is not None
    assert _matches(pattern, "Mini PC Intel N100 16GB")
    print("  [OK] non-regressione mini-pc (pcs intatto)")


def test_non_regression_gaming_headset():
    """NON-REGRESSIONE gaming headset: 'best budget gaming headset 2026' ->
    matcha una cuffia gaming over-ear vera."""
    primary = "best budget gaming headset 2026"
    clean = _clean_search_kw(primary)
    pattern = _resolve_topic_pattern(primary, clean)
    assert pattern is not None
    assert _matches(pattern, "Gaming Headset Over Ear with Microphone")
    print("  [OK] non-regressione gaming headset")


def test_non_regression_earbuds():
    """NON-REGRESSIONE earbuds: 'best wireless earbuds for running' -> matcha
    un titolo earbuds/TWS."""
    primary = "best wireless earbuds for running"
    clean = _clean_search_kw(primary)
    pattern = _resolve_topic_pattern(primary, clean)
    assert pattern is not None
    assert _matches(pattern, "TWS Wireless Earbuds Bluetooth Sport")
    print("  [OK] non-regressione earbuds")


def main() -> int:
    tests = [
        test_fix_speaker_under_30_dollars,
        test_regression_currency_other_niche,
        test_non_regression_mini_pc,
        test_non_regression_gaming_headset,
        test_non_regression_earbuds,
    ]
    for t in tests:
        t()
    print("OK - tutti i test passano (fix valuta + 4 non-regressioni)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
