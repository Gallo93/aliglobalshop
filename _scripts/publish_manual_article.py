"""Publish ONE pre-written blog article (all active languages) without any API call.

Fallback path for when the Anthropic credit is exhausted and generate_blog.py
exits 5 producing nothing. The article is hand-written by Claude Code into a
staging folder and this script promotes it to its destination, marks the topic
calendar as used, and primes the translate cache so the normal Claude translate
flow will NOT overwrite the native translations once the credit returns.

It does NOT touch generate_blog.py nor the normal flow: it is a parallel route.
Pure stdlib, no network, no external dependencies.

Staging layout (one article at a time):
    _data/blog/_manual/en.json   (mandatory)
    _data/blog/_manual/it.json   (mandatory for every active non-en language)
    _data/blog/_manual/es.json
    _data/blog/_manual/de.json
    _data/blog/_manual/fr.json

Each staging file is a complete article object with the generate_blog schema:
    title, slug, content_html, lang, meta_desc, category, primary_keyword

Flow (validate-everything-then-write, atomic): the script validates every file
first and writes NOTHING if any check fails. On success it writes
_data/blog/<lang>/<today>-<slug>.json for each active language, marks the
matching calendar topic used, updates _data/.translate_cache.json with the same
key/hash contract as translate_content.py, clears the staging files and exits 0.

Usage:
    python _scripts/publish_manual_article.py
    python _scripts/publish_manual_article.py --dry-run
"""
import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from generate_blog import topic_key_for_item, _topic_key  # noqa: E402

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "_data"
BLOG_DIR = DATA_DIR / "blog"
CALENDAR_PATH = DATA_DIR / "blog-calendar-en.json"
CONFIG_PATH = DATA_DIR / "config.json"
CACHE_PATH = DATA_DIR / ".translate_cache.json"

# Em-dash banned in any user-visible site text (see CLAUDE.md conventions).
EM_DASH = "—"

# Niche fallback if config.json has no "niches" list (mirrors CLAUDE.md niches).
_NICHE_FALLBACK = ["electronics", "smart-home", "sport", "gadgets"]

# Article fields that must be present and non-empty in every staging file.
_REQUIRED_FIELDS = ("title", "slug", "content_html", "meta_desc",
                    "category", "primary_keyword")

# Hard limits (mirror generate_blog STRICT REQUIREMENTS).
_META_MAX = 155
_EN_TITLE_MAX = 43
_OTHER_TITLE_WARN = 60
_SLUG_MAX = 60


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:  # noqa: BLE001
        print(f"[manual] cannot parse {path}: {exc}", file=sys.stderr)
        return default


def write_json(path: Path, data) -> None:
    """Write JSON the same way translate_content.write_json does: indent=2,
    ensure_ascii=False and a trailing newline (byte-coherent with the cache)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def active_languages(config: dict) -> list:
    langs = config.get("languages") or ["en"]
    if "en" not in langs:
        langs = ["en"] + list(langs)
    return list(langs)


def known_niches(config: dict) -> list:
    return config.get("niches") or _NICHE_FALLBACK


def staging_dir() -> Path:
    return BLOG_DIR / "_manual"


def existing_slug_in_lang(lang: str, slug: str) -> bool:
    """True if an article with this slug already exists in blog/<lang>/ under any
    date (mirrors generate_blog.slug_exists, scanning the slug field)."""
    lang_dir = BLOG_DIR / lang
    if not lang_dir.exists():
        return False
    for path in lang_dir.glob("*.json"):
        try:
            with open(path, encoding="utf-8") as f:
                if json.load(f).get("slug") == slug:
                    return True
        except (json.JSONDecodeError, OSError):
            continue
    return False


def load_staging(languages: list, errors: list) -> dict:
    """Load every active-language staging file. en is mandatory; every active
    non-en language is mandatory too. Missing/invalid -> error (no read)."""
    staging = {}
    sdir = staging_dir()
    for lang in languages:
        path = sdir / f"{lang}.json"
        if not path.exists():
            errors.append(f"staging file mancante: {path.relative_to(BASE_DIR)} "
                          f"(richiesto per la lingua attiva '{lang}')")
            continue
        data = load_json(path)
        if not isinstance(data, dict):
            errors.append(f"staging file illeggibile o non-oggetto: "
                          f"{path.relative_to(BASE_DIR)}")
            continue
        staging[lang] = data
    return staging


def validate(staging: dict, languages: list, niches: list,
             errors: list, warnings: list) -> None:
    """Collect ALL validation errors (and warnings) without writing anything."""
    if "en" not in staging:
        errors.append("en.json e' obbligatorio e manca o non e' valido")

    slugs = set()
    for lang in languages:
        data = staging.get(lang)
        if data is None:
            continue  # missing-file error already recorded by load_staging

        for field in _REQUIRED_FIELDS:
            value = data.get(field)
            if not (isinstance(value, str) and value.strip()):
                errors.append(f"{lang}.json: campo obbligatorio mancante o vuoto: "
                              f"'{field}'")

        if data.get("lang") != lang:
            errors.append(f"{lang}.json: campo 'lang' = {data.get('lang')!r}, "
                          f"atteso {lang!r}")

        slug = data.get("slug") or ""
        slugs.add(slug)

        # Slug format (only on en is enough since all must match, but check each).
        if slug:
            if not all(c.isascii() and (c.islower() or c.isdigit() or c == "-")
                       for c in slug):
                errors.append(f"{lang}.json: slug {slug!r} contiene caratteri non "
                              f"ammessi (solo [a-z0-9-] ASCII)")
            if len(slug) > _SLUG_MAX:
                errors.append(f"{lang}.json: slug {slug!r} lungo {len(slug)} > "
                              f"{_SLUG_MAX}")

        # Category must be a known niche.
        category = data.get("category") or ""
        if category and category not in niches:
            errors.append(f"{lang}.json: category {category!r} non e' una nicchia "
                          f"nota {niches}")

        # No em-dash anywhere visible.
        for field in ("title", "meta_desc", "content_html"):
            text = data.get(field) or ""
            if EM_DASH in text:
                errors.append(f"{lang}.json: em-dash (—) vietato nel campo "
                              f"'{field}'")

        # meta_desc length (hard limit, STRICT standard di generate_blog).
        meta = data.get("meta_desc") or ""
        if len(meta) > _META_MAX:
            errors.append(f"{lang}.json: meta_desc {len(meta)} char > {_META_MAX}")

        # Title length.
        title = data.get("title") or ""
        if lang == "en":
            if len(title) > _EN_TITLE_MAX:
                errors.append(f"en.json: title {len(title)} char > "
                              f"{_EN_TITLE_MAX}")
        elif len(title) > _OTHER_TITLE_WARN:
            warnings.append(f"{lang}.json: title {len(title)} char > "
                            f"{_OTHER_TITLE_WARN} (le lingue sono piu' lunghe, "
                            f"non bloccante)")

    # All files must share the same slug.
    present_slugs = {s for s in slugs if s}
    if len(present_slugs) > 1:
        errors.append(f"slug diversi tra le lingue: {sorted(present_slugs)} "
                      f"(devono coincidere)")


def mark_calendar(en_primary_keyword: str, today: str, dry_run: bool) -> None:
    """Mark the first unused calendar topic whose canonical key matches the EN
    primary_keyword. Not found -> warning (still publishes)."""
    items = load_json(CALENDAR_PATH, default=None)
    if not isinstance(items, list):
        print(f"[manual] [warn] calendario assente o illeggibile a "
              f"{CALENDAR_PATH}, salto la marcatura", file=sys.stderr)
        return
    target_key = _topic_key(en_primary_keyword)
    for item in items:
        if not isinstance(item, dict) or item.get("used"):
            continue
        if target_key and topic_key_for_item(item) == target_key:
            print(f"[manual] calendario: topic {item.get('topic')!r} "
                  f"marcato used (key {target_key!r})")
            if not dry_run:
                item["used"] = True
                item["used_at"] = today
                write_json(CALENDAR_PATH, items)
            return
    print(f"[manual] [warn] nessun topic non-usato combacia con la key "
          f"{target_key!r}: l'articolo si pubblica comunque, calendario "
          f"invariato", file=sys.stderr)


def update_translate_cache(en_disk_path: Path, slug: str, today: str,
                           non_en_langs: list, dry_run: bool) -> dict:
    """Prime .translate_cache.json so the Claude translate flow skips these
    natively-translated files. Replicates translate_content's contract exactly:
      key   = "blog/<lang>/<today>-<slug>.json"
      value = sha256(json.dumps(en_data, ensure_ascii=False, sort_keys=True))
    where en_data is the EN article AS WRITTEN ON DISK (loaded back to be
    byte-coherent with translate_content, which hashes its src file)."""
    en_data = load_json(en_disk_path)
    raw = json.dumps(en_data, ensure_ascii=False, sort_keys=True)
    h = source_hash(raw)
    cache = load_json(CACHE_PATH, default={}) or {}
    written = {}
    for lang in non_en_langs:
        key = f"blog/{lang}/{today}-{slug}.json"
        cache[key] = h
        written[key] = h
    if not dry_run:
        write_json(CACHE_PATH, cache)
    return written


def clean_staging(languages: list, dry_run: bool) -> None:
    """Delete the promoted _manual/*.json files, keep the folder via .gitkeep."""
    sdir = staging_dir()
    for lang in languages:
        path = sdir / f"{lang}.json"
        if path.exists() and not dry_run:
            path.unlink()
    if not dry_run:
        gitkeep = sdir / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.parent.mkdir(parents=True, exist_ok=True)
            gitkeep.write_text("", encoding="utf-8")


def run(dry_run: bool) -> int:
    config = load_json(CONFIG_PATH, default={}) or {}
    languages = active_languages(config)
    niches = known_niches(config)

    errors, warnings = [], []
    staging = load_staging(languages, errors)
    if staging:
        validate(staging, languages, niches, errors, warnings)

    # Duplicate guard: refuse if any active language already has this slug.
    en = staging.get("en") or {}
    slug = (en.get("slug") or "").strip()
    if slug and not errors:
        for lang in languages:
            if existing_slug_in_lang(lang, slug):
                errors.append(f"slug {slug!r} gia' presente in blog/{lang}/ "
                              f"(duplicato): non pubblico")

    for w in warnings:
        print(f"[manual] [warn] {w}", file=sys.stderr)

    if errors:
        print(f"[manual] VALIDAZIONE FALLITA ({len(errors)} errori), "
              f"nessun file scritto:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    today = date.today().isoformat()
    non_en_langs = [l for l in languages if l != "en"]

    print(f"[manual] {'(dry-run) ' if dry_run else ''}pubblico articolo "
          f"slug={slug!r} data={today} lingue={languages}")

    # Write every active-language destination file (en first, so the cache can
    # load it back byte-coherently afterwards).
    en_disk_path = BLOG_DIR / "en" / f"{today}-{slug}.json"
    for lang in languages:
        data = dict(staging[lang])
        data["date"] = today
        data["lang"] = lang
        dst = BLOG_DIR / lang / f"{today}-{slug}.json"
        print(f"[manual] {'(dry-run) ' if dry_run else ''}-> "
              f"{dst.relative_to(BASE_DIR).as_posix()}")
        if not dry_run:
            write_json(dst, data)

    if dry_run:
        # Show what the cache/calendar would do without touching disk.
        mark_calendar(en.get("primary_keyword", ""), today, dry_run=True)
        for lang in non_en_langs:
            print(f"[manual] (dry-run) cache key -> "
                  f"blog/{lang}/{today}-{slug}.json")
        print("[manual] (dry-run) nessuna scrittura eseguita.")
        return 0

    written_cache = update_translate_cache(en_disk_path, slug, today,
                                           non_en_langs, dry_run=False)
    mark_calendar(en.get("primary_keyword", ""), today, dry_run=False)
    clean_staging(languages, dry_run=False)

    print(f"[manual] FATTO: {len(languages)} file pubblicati, "
          f"{len(written_cache)} chiavi cache aggiornate, staging ripulita.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publish one pre-written blog article (all languages), no API.")
    parser.add_argument("--dry-run", action="store_true",
                        help="valida e mostra cosa farebbe senza scrivere nulla")
    args = parser.parse_args()
    sys.exit(run(args.dry_run))


if __name__ == "__main__":
    main()
