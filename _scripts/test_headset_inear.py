"""Test deterministico (no API, no rete) dell'esclusione in-ear condizionale
di fetch_products.py.

Un topic "headset" (cuffie gaming over-ear con boom-mic) NON deve mostrare
auricolari IEM/earphone/earbud/earplug in-ear; deve tenere le cuffie over-ear
(headset/headphone). La guardia condizionale garantisce che un topic
"earbuds" (es. "wireless earbuds for running") NON perda gli earbuds.

Eseguibile a mano (`python _scripts/test_headset_inear.py`) o via pytest.
Esce con codice != 0 al primo fallimento.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fetch_products as fp  # noqa: E402


def _clean(primary_keyword: str, title: str = "") -> str:
    """pattern_kw come in fetch_article_products."""
    return fp._clean_search_kw(primary_keyword) or fp._clean_search_kw(title)


def _pattern_for(primary_keyword: str, title: str = ""):
    combined = f"{title} {primary_keyword}"
    return fp._resolve_topic_pattern(combined, _clean(primary_keyword, title))


def _keep(primary_keyword: str, product_title: str) -> bool:
    """Replica la decisione di fetch_article_products per l'esclusione in-ear +
    pertinenza: True se il prodotto sopravvive (pertinente e non escluso)."""
    clean_kw = _clean(primary_keyword)
    pattern = _pattern_for(primary_keyword)
    exclude_inear = fp._should_exclude_inear(clean_kw)
    if exclude_inear and fp._is_inear_form(product_title):
        return False
    return fp._is_relevant(product_title, pattern)


# (primary_keyword, product_title, atteso-mantenuto)
CASES = [
    # --- Topic HEADSET: gli in-ear vanno esclusi, le over-ear tenute ----------
    ("best budget gaming headset 2026",
     "KZ PRO 24 HiFi IEM Earbud In Ear Monitor Wired Earphone", False),
    ("best budget gaming headset 2026",
     "Zhulinniao Z5 Wired Earphones In Ear Earplugs HiFi", False),
    ("best budget gaming headset 2026",
     "EKSA E900 Gaming Headset Over Ear with Microphone Noise Cancelling", True),
    ("best budget gaming headset 2026",
     "Oneodio Gaming Headphones Over Ear Wired 50mm Driver", True),

    # --- REGRESSIONE topic EARBUDS: gli earbuds/IEM RESTANO pertinenti --------
    ("best wireless earbuds for running",
     "TWS Wireless Bluetooth Earbuds In Ear Sport Waterproof", True),
    ("best wireless earbuds for running",
     "KZ PRO 24 HiFi IEM Earbud In Ear Monitor Wired Earphone", True),
]


def main() -> int:
    failures = []

    for primary_kw, title, expected_keep in CASES:
        got = _keep(primary_kw, title)
        tag = "KEEP" if expected_keep else "DROP"
        if got != expected_keep:
            failures.append(
                f"{primary_kw!r}: {title!r} atteso {tag}, ottenuto "
                f"{'KEEP' if got else 'DROP'}")
        else:
            print(f"[ok] {tag}: {primary_kw!r} <- {title!r}")

    # La guardia condizionale: headset -> esclusione ON; earbuds -> OFF.
    if not fp._should_exclude_inear(_clean("best budget gaming headset 2026")):
        failures.append("topic headset: _should_exclude_inear doveva essere True")
    else:
        print("[ok] guardia: esclusione in-ear ON per topic headset")
    if fp._should_exclude_inear(_clean("best wireless earbuds for running")):
        failures.append("topic earbuds: _should_exclude_inear doveva essere False")
    else:
        print("[ok] guardia: esclusione in-ear OFF per topic earbuds")

    # 'headphone'/'headset' non sono form in-ear; 'over ear' non e' 'in ear'.
    over_ear_ok = True
    for over_ear in ("Gaming Headset Over Ear with Microphone",
                     "Gaming Headphones Over Ear Wired"):
        if fp._is_inear_form(over_ear):
            failures.append(f"{over_ear!r} NON e' in-ear (over-ear valido)")
            over_ear_ok = False
    if over_ear_ok:
        print("[ok] over-ear headset/headphones non classificati in-ear")

    # Non-regressione altri topic gia' coperti (mini pc, gaming mouse): nessuna
    # esclusione in-ear e pertinenza invariata.
    for primary_kw, good_title in (
        ("are cheap mini pcs worth it",
         "Intel N100 Mini PC 16GB DDR4 512GB Windows 11"),
        ("best gaming mouse 2026",
         "RGB Wired Gaming Mouse 12000 DPI Programmable"),
    ):
        if fp._should_exclude_inear(_clean(primary_kw)):
            failures.append(f"{primary_kw!r}: esclusione in-ear non doveva attivarsi")
        if not _keep(primary_kw, good_title):
            failures.append(f"{primary_kw!r}: {good_title!r} doveva restare pertinente")
        else:
            print(f"[ok] non-regressione: {primary_kw!r} <- {good_title!r}")

    print()
    if failures:
        print(f"FALLITI {len(failures)} controlli:")
        for f in failures:
            print("  -", f)
        return 1
    print("TUTTI I CONTROLLI PASSATI")
    return 0


def test_headset_inear():
    """Entry-point pytest."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
