"""Test deterministico (no API, no rete) di publish_manual_article.py.

Ogni test costruisce una mini-struttura `_data/` di fixture in una cartella
temporanea e monkeypatcha le costanti di path del modulo verso la tmp, cosi i
dati reali del repo non vengono mai toccati. La chiave/hash della translate
cache viene RICALCOLATA in modo indipendente (riusando `source_hash` di
translate_content e lo stesso `raw = json.dumps(..., sort_keys=True)`) per
garantire che il flusso Claude normale salti la ri-traduzione.

Eseguibile a mano (`python _scripts/test_publish_manual_article.py`) o via
pytest. Esce con codice != 0 al primo fallimento.
"""
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import publish_manual_article as pma  # noqa: E402
from translate_content import source_hash as tc_source_hash  # noqa: E402

LANGS = ["en", "it", "es", "de", "fr"]
TODAY = date.today().isoformat()
SLUG = "aliexpress-running-earbuds-2026"
EN_KEYWORD = "aliexpress running earbuds"

_CONTENT = ("<h1>{t}</h1><p>Some buying advice for runners who want cheap "
            "earbuds under $30. Browse all deals here.</p>"
            "<h2>What to Look For</h2><p>Sweat resistance, fit, battery.</p>"
            "<div class=\"faq\"><details><summary>Are they good?</summary>"
            "<p>Yes, for the price.</p></details></div>")


def _article(lang: str, title: str, **over) -> dict:
    data = {
        "title": title,
        "slug": SLUG,
        "content_html": _CONTENT.format(t=title),
        "lang": lang,
        "meta_desc": "Cheap AliExpress running earbuds for 2026, picks under $30.",
        "category": "sport",
        "primary_keyword": EN_KEYWORD if lang == "en"
        else "auricolari running aliexpress",
    }
    data.update(over)
    return data


def _default_staging() -> dict:
    return {
        "en": _article("en", "Best AliExpress Running Earbuds 2026"),
        "it": _article("it", "Migliori auricolari running AliExpress 2026"),
        "es": _article("es", "Mejores auriculares running AliExpress 2026"),
        "de": _article("de", "Beste AliExpress Running-Earbuds 2026"),
        "fr": _article("fr", "Meilleurs ecouteurs running AliExpress 2026"),
    }


def _setup(tmp: Path, staging: dict, calendar=None, seed_dup_lang=None):
    """Costruisce _data/ di fixture e patcha le costanti di pma verso tmp."""
    data = tmp / "_data"
    (data / "blog" / "_manual").mkdir(parents=True)
    for lang in LANGS:
        (data / "blog" / lang).mkdir(parents=True)

    config = {
        "site_url": "https://example.test",
        "languages": LANGS,
        "niches": ["electronics", "smart-home", "sport", "gadgets"],
    }
    (data / "config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    if calendar is None:
        calendar = [
            {"topic": "AliExpress running earbuds", "primary_keyword": EN_KEYWORD,
             "category": "sport", "intent": "commercial", "used": False},
            {"topic": "AliExpress smart plug", "primary_keyword": "aliexpress smart plug",
             "category": "smart-home", "intent": "commercial", "used": False},
        ]
    (data / "blog-calendar-en.json").write_text(
        json.dumps(calendar, ensure_ascii=False, indent=2), encoding="utf-8")

    for lang, art in staging.items():
        (data / "blog" / "_manual" / f"{lang}.json").write_text(
            json.dumps(art, ensure_ascii=False, indent=2), encoding="utf-8")

    if seed_dup_lang:
        (data / "blog" / seed_dup_lang / f"2020-01-01-{SLUG}.json").write_text(
            json.dumps({"slug": SLUG, "lang": seed_dup_lang}, ensure_ascii=False),
            encoding="utf-8")

    pma.BASE_DIR = tmp
    pma.DATA_DIR = data
    pma.BLOG_DIR = data / "blog"
    pma.CALENDAR_PATH = data / "blog-calendar-en.json"
    pma.CONFIG_PATH = data / "config.json"
    pma.CACHE_PATH = data / ".translate_cache.json"
    return data


def _dest(data: Path, lang: str) -> Path:
    return data / "blog" / lang / f"{TODAY}-{SLUG}.json"


def _run_in_tmp(staging, **setup_kw):
    tmp = Path(tempfile.mkdtemp(prefix="pma-test-"))
    data = _setup(tmp, staging, **setup_kw)
    return data, tmp


# --- happy path --------------------------------------------------------------

def test_happy_path():
    data, _ = _run_in_tmp(_default_staging())
    rc = pma.run(dry_run=False)
    assert rc == 0, f"happy path deve uscire 0, uscito {rc}"

    for lang in LANGS:
        dest = _dest(data, lang)
        assert dest.exists(), f"manca il file destinazione {lang}"
        obj = json.loads(dest.read_text(encoding="utf-8"))
        assert obj["date"] == TODAY, f"{lang}: date errata"
        assert obj["lang"] == lang, f"{lang}: lang errata"
        assert obj["slug"] == SLUG

    # calendario marcato
    cal = json.loads((data / "blog-calendar-en.json").read_text(encoding="utf-8"))
    assert cal[0]["used"] is True, "topic combaciante deve essere used"
    assert cal[0].get("used_at") == TODAY, "used_at deve essere oggi"
    assert cal[1]["used"] is False, "topic non combaciante resta unused"

    # cache: chiave/hash combacia col contratto di translate_content
    cache = json.loads((data / ".translate_cache.json").read_text(encoding="utf-8"))
    en_disk = json.loads(_dest(data, "en").read_text(encoding="utf-8"))
    raw = json.dumps(en_disk, ensure_ascii=False, sort_keys=True)
    expected = tc_source_hash(raw)
    for lang in ["it", "es", "de", "fr"]:
        key = f"blog/{lang}/{TODAY}-{SLUG}.json"
        assert key in cache, f"manca la cache key {key}"
        assert cache[key] == expected, f"hash cache {lang} != contratto translate"
    assert f"blog/en/{TODAY}-{SLUG}.json" not in cache, "en non deve avere cache key"

    # staging svuotata
    sdir = data / "blog" / "_manual"
    for lang in LANGS:
        assert not (sdir / f"{lang}.json").exists(), f"staging {lang} non rimossa"
    assert (sdir / ".gitkeep").exists(), "manca .gitkeep nella staging"
    print("[ok] happy path: 5 file, calendario, cache, staging puliti")


# --- atomicita': lingua mancante ---------------------------------------------

def test_reject_missing_language():
    staging = _default_staging()
    del staging["es"]
    data, _ = _run_in_tmp(staging)
    rc = pma.run(dry_run=False)
    assert rc != 0, "lingua mancante deve fallire"
    for lang in LANGS:
        assert not _dest(data, lang).exists(), f"NESSUN file deve essere scritto ({lang})"
    assert not (data / ".translate_cache.json").exists(), "cache non deve essere scritta"
    print("[ok] reject: lingua mancante, atomicita' rispettata")


# --- em-dash -----------------------------------------------------------------

def test_reject_em_dash():
    staging = _default_staging()
    staging["it"]["content_html"] += "<p>Prezzo basso — ottimo affare.</p>"
    data, _ = _run_in_tmp(staging)
    rc = pma.run(dry_run=False)
    assert rc != 0, "em-dash deve fallire"
    assert not _dest(data, "it").exists()
    print("[ok] reject: em-dash")


# --- slug non valido ---------------------------------------------------------

def test_reject_bad_slug_nonascii():
    staging = _default_staging()
    for art in staging.values():
        art["slug"] = "aliexpress-running-éarbuds"
    data, _ = _run_in_tmp(staging)
    rc = pma.run(dry_run=False)
    assert rc != 0, "slug non-ascii deve fallire"
    print("[ok] reject: slug non-ascii")


def test_reject_slug_too_long():
    staging = _default_staging()
    long_slug = "aliexpress-" + "x" * 60
    for art in staging.values():
        art["slug"] = long_slug
    data, _ = _run_in_tmp(staging)
    rc = pma.run(dry_run=False)
    assert rc != 0, "slug >60 deve fallire"
    print("[ok] reject: slug troppo lungo")


# --- title EN troppo lungo ---------------------------------------------------

def test_reject_en_title_too_long():
    staging = _default_staging()
    staging["en"]["title"] = "The Absolute Best AliExpress Running Earbuds You Can Buy 2026"
    data, _ = _run_in_tmp(staging)
    rc = pma.run(dry_run=False)
    assert rc != 0, "title EN >43 deve fallire"
    print("[ok] reject: title EN troppo lungo")


# --- slug duplicato ----------------------------------------------------------

def test_reject_duplicate_slug():
    data, _ = _run_in_tmp(_default_staging(), seed_dup_lang="en")
    rc = pma.run(dry_run=False)
    assert rc != 0, "slug duplicato deve fallire"
    assert not _dest(data, "en").exists(), "non deve scrivere il file odierno"
    print("[ok] reject: slug duplicato gia' in blog/en")


# --- calendario: topic non trovato -> warning ma pubblica --------------------

def test_calendar_no_match_still_publishes():
    calendar = [
        {"topic": "AliExpress smart plug", "primary_keyword": "aliexpress smart plug",
         "category": "smart-home", "used": False},
    ]
    data, _ = _run_in_tmp(_default_staging(), calendar=calendar)
    rc = pma.run(dry_run=False)
    assert rc == 0, "topic non trovato: deve comunque pubblicare (exit 0)"
    assert _dest(data, "en").exists(), "l'articolo deve essere pubblicato"
    cal = json.loads((data / "blog-calendar-en.json").read_text(encoding="utf-8"))
    assert cal[0]["used"] is False, "nessun topic deve essere marcato used"
    print("[ok] calendario: nessun match -> warning, pubblica comunque")


# --- dry-run non scrive ------------------------------------------------------

def test_dry_run_writes_nothing():
    data, _ = _run_in_tmp(_default_staging())
    rc = pma.run(dry_run=True)
    assert rc == 0, "dry-run valido deve uscire 0"
    for lang in LANGS:
        assert not _dest(data, lang).exists(), f"dry-run non deve scrivere ({lang})"
    assert not (data / ".translate_cache.json").exists(), "dry-run non scrive cache"
    cal = json.loads((data / "blog-calendar-en.json").read_text(encoding="utf-8"))
    assert cal[0]["used"] is False, "dry-run non marca il calendario"
    sdir = data / "blog" / "_manual"
    assert (sdir / "en.json").exists(), "dry-run non deve svuotare la staging"
    print("[ok] dry-run: nessuna scrittura")


_TESTS = [
    test_happy_path,
    test_reject_missing_language,
    test_reject_em_dash,
    test_reject_bad_slug_nonascii,
    test_reject_slug_too_long,
    test_reject_en_title_too_long,
    test_reject_duplicate_slug,
    test_calendar_no_match_still_publishes,
    test_dry_run_writes_nothing,
]


def main() -> int:
    failures = []
    for t in _TESTS:
        try:
            t()
        except AssertionError as exc:
            failures.append(f"{t.__name__}: {exc}")
            print(f"[FAIL] {t.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{t.__name__}: {type(exc).__name__}: {exc}")
            print(f"[ERROR] {t.__name__}: {type(exc).__name__}: {exc}")
    print()
    if failures:
        print(f"FALLITI {len(failures)} test:")
        for f in failures:
            print("  -", f)
        return 1
    print(f"TUTTI I {len(_TESTS)} TEST PASSATI")
    return 0


if __name__ == "__main__":
    sys.exit(main())
