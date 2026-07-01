"""Test deterministico (no API, no rete) del pattern-tema DINAMICO
plural-tolerant di fetch_products.py.

Verifica che il sostantivo-testa plurale ('pcs') matchi il singolare dei titoli
prodotto ('Mini PC') e che i temi esistenti restino pertinenti.

Eseguibile a mano (`python _scripts/test_mini_pc_relevance.py`) o via pytest.
Esce con codice != 0 al primo fallimento.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fetch_products as fp  # noqa: E402


def _pattern_for(primary_keyword: str, title: str = ""):
    """Risolve il pattern-tema come fetch_article_products: pattern_kw dalla
    primary_keyword (o dal titolo), combined = titolo + primary_keyword."""
    combined = f"{title} {primary_keyword}"
    clean_kw = fp._clean_search_kw(primary_keyword) or fp._clean_search_kw(title)
    return fp._resolve_topic_pattern(combined, clean_kw)


# (primary_keyword, titolo pertinente atteso, titolo off-topic atteso)
RELEVANT_CASES = [
    (
        "are cheap mini pcs worth it",
        "Intel N100 Mini PC 16GB DDR4 512GB Windows 11 Desktop Computer",
        "Wireless Bluetooth Earbuds TWS",
    ),
    (
        "best gaming mouse 2026",
        "RGB Wired Gaming Mouse 12000 DPI Programmable",
        "Wireless Bluetooth Earbuds TWS",
    ),
    (
        "are cheap drones worth it",
        "4K HD Camera Drone GPS Foldable Quadcopter",
        "Stainless Steel Water Bottle 750ml",
    ),
    (
        "aliexpress mechanical keyboard guide",
        "Mechanical Keyboard 87 Keys Hot Swap RGB Backlit",
        "Wireless Bluetooth Earbuds TWS",
    ),
]


def main() -> int:
    failures = []
    for primary_kw, good_title, bad_title in RELEVANT_CASES:
        pattern = _pattern_for(primary_kw)
        if pattern is None:
            failures.append(f"pattern None per {primary_kw!r}")
            continue
        if not fp._is_relevant(good_title, pattern):
            failures.append(
                f"{primary_kw!r}: {good_title!r} doveva essere PERTINENTE")
        else:
            print(f"[ok] pertinente: {primary_kw!r} <- {good_title!r}")
        if fp._is_relevant(bad_title, pattern):
            failures.append(
                f"{primary_kw!r}: {bad_title!r} NON doveva essere pertinente")
        else:
            print(f"[ok] off-topic scartato: {primary_kw!r} <- {bad_title!r}")

    # Il token-testa plurale ('pcs') deve matchare il singolare 'PC' dei titoli.
    pcs_pattern = _pattern_for("are cheap mini pcs worth it")
    if pcs_pattern is None or not pcs_pattern.search("Mini PC"):
        failures.append("pattern 'pcs' deve matchare 'Mini PC' (singolare)")
    else:
        print("[ok] 'pcs' matcha 'Mini PC' (singolare/plurale tollerante)")

    print()
    if failures:
        print(f"FALLITI {len(failures)} controlli:")
        for f in failures:
            print("  -", f)
        return 1
    print("TUTTI I CONTROLLI PASSATI")
    return 0


def test_mini_pc_relevance():
    """Entry-point pytest."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
