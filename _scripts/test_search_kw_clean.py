"""Test deterministico (no API, no rete) di _clean_search_kw di fetch_products.py.

Verifica che la pulizia della keyword di ricerca tolga le parole-domanda/guida
dei topic informativi (how/what/choose/worth/...) lasciando il sostantivo, e che
i topic gia' product-like restino INVARIATI (nessun sostantivo-prodotto perso).

Eseguibile a mano (`python _scripts/test_search_kw_clean.py`) o via pytest.
Esce con codice != 0 al primo fallimento.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fetch_products import _clean_search_kw  # noqa: E402

# (input, output atteso). I topic informativi devono ridursi al sostantivo;
# i topic product-like restano identici al comportamento precedente.
CASES = [
    ("how to choose a portable monitor", "portable monitor"),
    ("what to look for in a budget projector", "budget projector"),
    ("are budget massage guns worth it", "budget massage guns"),
    ("how to build a budget home gym", "budget home gym"),
    # INVARIATI (product-like): non devono cambiare.
    ("best wireless earbuds for running", "wireless earbuds running"),
    ("aliexpress smart home gadgets", "smart home gadgets"),
]

# Casi-guardia: il sostantivo-testa atteso deve sopravvivere alla pulizia di un
# how-to (non venire scambiato per stopword).
HEAD_NOUN_SURVIVES = [
    ("how to choose a portable monitor", "monitor"),
    ("what to look for in a budget projector", "projector"),
    ("how to build a budget home gym", "gym"),
    ("are budget massage guns worth it", "guns"),
]


def main() -> int:
    failures = []

    for text, expected in CASES:
        got = _clean_search_kw(text)
        if got != expected:
            failures.append(f"{text!r} -> {got!r}, atteso {expected!r}")
        else:
            print(f"[ok] {text!r} -> {got!r}")

    for text, noun in HEAD_NOUN_SURVIVES:
        got = _clean_search_kw(text)
        if noun not in got.split():
            failures.append(f"sostantivo {noun!r} perso da {text!r} -> {got!r}")
        else:
            print(f"[ok] sostantivo {noun!r} presente in {got!r}")

    print()
    if failures:
        print(f"FALLITI {len(failures)} controlli:")
        for f in failures:
            print("  -", f)
        return 1
    print("TUTTI I CONTROLLI PASSATI")
    return 0


def test_search_kw_clean():
    """Entry-point pytest."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
