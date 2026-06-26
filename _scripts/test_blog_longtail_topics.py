"""Test deterministico (no API, no rete) dei topic long-tail del calendario blog.

Riorienta i topic in coda (used == false) da query brand-navigazionali
("aliexpress + categoria", dove l'utente cerca AliExpress stesso e il sito non
rankera mai) a query problema/scelta/confronto long-tail, dove aliglobalshop puo
davvero posizionarsi. I topic gia' pubblicati (used == true) restano storia e
NON vengono controllati: non si possono de-pubblicare.

Verifica, su OGNI topic ancora in coda di _data/blog-calendar-en.json:
  a) la category e' una delle 4 nicchie valide (il match prodotti dipende da questo);
  b) lo slug derivato dal primary_keyword e' ASCII, <= 60 char (vincolo slug del sito);
  c) il primary_keyword (la query-target) NON inizia con "aliexpress"
     (niente piu query brand-navigazionali a CTR zero);
  d) nessun doppione di head-topic in coda: le topic-key di generate_blog._topic_key
     sono tutte distinte, cosi il guard anti-cannibalizzazione (PR #29) non taglia
     i nuovi topic ne ne lascia passare due quasi-gemelli.

Eseguibile a mano (`python _scripts/test_blog_longtail_topics.py`) o via pytest.
Esce con codice != 0 al primo fallimento.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from generate_blog import _topic_key, slugify, topic_key_for_item  # noqa: E402

CALENDAR_PATH = Path(__file__).parent.parent / "_data" / "blog-calendar-en.json"

VALID_NICHES = {"electronics", "smart-home", "sport", "gadgets"}

# Soglia minima di topic long-tail in coda: la PR ne introduce ~24. Sotto questa
# soglia qualcosa ha svuotato la coda per sbaglio.
MIN_QUEUED_TOPICS = 15


def _is_ascii(text: str) -> bool:
    try:
        text.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def main() -> int:
    with open(CALENDAR_PATH, encoding="utf-8") as f:
        items = json.load(f)

    queued = [it for it in items if not it.get("used")]
    failures = []

    if len(queued) < MIN_QUEUED_TOPICS:
        failures.append(
            f"[setup] solo {len(queued)} topic in coda, attesi >= {MIN_QUEUED_TOPICS}"
        )

    seen_keys = {}
    for it in queued:
        topic = it.get("topic", "")
        pk = (it.get("primary_keyword") or "").strip()

        # (a) nicchia valida
        cat = it.get("category", "")
        if cat not in VALID_NICHES:
            failures.append(f"[a] nicchia non valida {cat!r} in topic {topic!r}")

        # (b) slug derivato ASCII e <= 60
        slug = slugify(pk or topic)
        if not _is_ascii(slug):
            failures.append(f"[b] slug non-ASCII {slug!r} in topic {topic!r}")
        if len(slug) > 60:
            failures.append(f"[b] slug troppo lungo ({len(slug)}) {slug!r} in topic {topic!r}")

        # (c) niente query brand-navigazionali: "aliexpress" prima parola del target
        first_word = pk.lower().split(" ", 1)[0] if pk else ""
        if first_word == "aliexpress":
            failures.append(
                f"[c] primary_keyword brand-navigazionale (inizia con 'aliexpress'): {pk!r}"
            )

        # (d) head-topic unico in coda
        key = topic_key_for_item(it)
        if not key:
            failures.append(f"[d] topic-key vuota per topic {topic!r}")
        elif key in seen_keys:
            failures.append(
                f"[d] head-topic doppione {key!r}: {topic!r} collide con {seen_keys[key]!r}"
            )
        else:
            seen_keys[key] = topic

    print(f"Topic in coda controllati: {len(queued)} (head-topic distinti: {len(seen_keys)})")
    print()
    if failures:
        print(f"FALLITI {len(failures)} controlli:")
        for fail in failures:
            print("  -", fail)
        return 1
    print("TUTTI I CONTROLLI PASSATI")
    return 0


def test_blog_longtail_topics():
    """Entry-point pytest."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
