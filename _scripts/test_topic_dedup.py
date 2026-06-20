"""Test deterministico (no API, no rete) del guard topic-level anti-cannibalizzazione.

Verifica che `_topic_key` di generate_blog.py:
  a) collassi ogni cluster di quasi-gemelle note su UNA sola chiave;
  b) NON collassi topic legittimamente diversi (vicini ma distinti);
  c) non produca mai una chiave vuota (fallback).

Eseguibile a mano (`python _scripts/test_topic_dedup.py`) o via pytest.
Esce con codice != 0 al primo fallimento.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from generate_blog import _topic_key  # noqa: E402

# (a) Cluster reali consolidati in questa PR: ogni lista DEVE avere 1 sola chiave.
# Si usano gli SLUG reali (cosi il test riflette esattamente i file in repo).
CLUSTERS = {
    "travel-gadgets": [
        "aliexpress-travel-gadgets-2026",
        "aliexpress-travel-gadgets-2026-guide",
        "aliexpress-travel-gadgets-2026-top-picks",
    ],
    "yoga-gear": [
        "aliexpress-yoga-gear-best-picks-2026",
        "aliexpress-yoga-gear-2026-guide",
        "aliexpress-yoga-gear-2026-best-buys",
    ],
    "bike-accessories": [
        "aliexpress-bike-accessories-2026",
        "aliexpress-bike-accessories-2026-top-picks",
    ],
    "smart-home-gadgets": [
        "aliexpress-smart-home-gadgets-2026",
        "aliexpress-smart-home-gadgets-2026-guide",
    ],
    "home-gym-equipment": [
        "aliexpress-home-gym-equipment-2026",
        "aliexpress-home-gym-equipment-2026-guide",
    ],
    "shipping-to-uk": [
        "aliexpress-shipping-to-uk-2026",
        "aliexpress-shipping-to-uk-2026-guide",
    ],
    # gia' consolidati in passato: confermano che il pattern e' coerente
    "smart-bulbs": [
        "aliexpress-smart-bulbs-reviews-2026",
        "aliexpress-smart-bulbs-reviews-2026-guide",
    ],
    "safe-uk": [
        "is-aliexpress-safe-uk-2026-buyers-guide",
        "is-aliexpress-safe-uk-2026-guide",
    ],
}

# (b) Coppie/triple "vicine ma diverse": le chiavi DEVONO restare distinte.
# Usano i primary_keyword reali del calendario.
DISTINCT_GROUPS = [
    ["aliexpress robot vacuum reviews", "aliexpress robot mop"],
    ["aliexpress smart bulbs reviews", "aliexpress smart light panels"],
    ["aliexpress smart plug", "aliexpress smart switch", "aliexpress smart thermostat"],
    ["aliexpress yoga gear", "aliexpress running gear"],
    ["aliexpress bike accessories", "aliexpress bike lights"],
    ["aliexpress travel gadgets", "aliexpress car gadgets", "aliexpress kitchen gadgets"],
    ["aliexpress home gym equipment", "aliexpress camping gear"],
    ["aliexpress shipping to uk", "aliexpress customs fees guide"],
]

# (c) Input degeneri: chiave mai vuota.
NEVER_EMPTY = [
    "the best 2026 guide",
    "top picks for 2026",
    "best buys 2026",
    "aliexpress 2026",
]


def main() -> int:
    failures = []

    # (a) collasso intra-cluster
    for name, members in CLUSTERS.items():
        keys = {_topic_key(m) for m in members}
        if len(keys) != 1:
            failures.append(
                f"[a] cluster {name!r} NON collassa: {len(keys)} chiavi distinte "
                f"-> { {m: _topic_key(m) for m in members} }"
            )
        else:
            print(f"[a] OK cluster {name:20s} -> chiave {next(iter(keys))!r}")

    # (b) cluster diversi non devono collidere tra loro
    cluster_keys = {name: _topic_key(members[0]) for name, members in CLUSTERS.items()}
    seen = {}
    for name, key in cluster_keys.items():
        if key in seen:
            failures.append(f"[b] cluster {name!r} e {seen[key]!r} collidono sulla chiave {key!r}")
        seen[key] = name

    # (b) coppie vicine ma diverse
    for group in DISTINCT_GROUPS:
        keys = [_topic_key(g) for g in group]
        if len(set(keys)) != len(keys):
            failures.append(
                f"[b] gruppo {group} NON distinto: { dict(zip(group, keys)) }"
            )
        else:
            print(f"[b] OK distinti: {group} -> {keys}")

    # (c) chiave mai vuota
    for text in NEVER_EMPTY:
        key = _topic_key(text)
        if not key.strip():
            failures.append(f"[c] chiave vuota per input {text!r}")
        else:
            print(f"[c] OK non-vuoto: {text!r} -> {key!r}")

    # input vuoto/None -> "" e' accettabile (il guard lo tratta come 'non blocca')
    assert _topic_key("") == "", "stringa vuota deve dare chiave vuota"
    assert _topic_key(None) == "", "None deve dare chiave vuota"

    print()
    if failures:
        print(f"FALLITI {len(failures)} controlli:")
        for f in failures:
            print("  -", f)
        return 1
    print("TUTTI I CONTROLLI PASSATI")
    return 0


def test_topic_dedup():
    """Entry-point pytest."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
