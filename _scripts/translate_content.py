"""
Translate EN content to a target language (default IT) with Argos Translate.

Sources translated:
  1. _data/products/<lang>/*.json   <- _data/products/en/*.json   (field: title)
     including the _article/*.json sub-folder.
  2. _data/blog/<lang>/*.json        <- _data/blog/en/*.json
     (fields: title, meta_desc / meta_description; content_html translating
      only HTML text nodes, never attributes such as href/src/class).

Prices, URLs, slugs, product ids and image URLs are never touched. Slugs stay
identical, so translated files keep the same file names as their EN source.

Idempotent: a per-file source hash is stored in _data/.translate_cache.json.
A file is re-translated only when its EN source changed (or with --force).

Usage:
    python _scripts/translate_content.py            # --lang it
    python _scripts/translate_content.py --lang it --force

The Argos en->target package must be installed beforehand (the CI step does
this). If the engine or package is missing, the script logs and exits without
overwriting any existing translation.
"""
import argparse
import hashlib
import json
import sys
from html.parser import HTMLParser
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "_data"
CACHE_PATH = DATA_DIR / ".translate_cache.json"

SOURCE_LANG = "en"

# Tags whose text content must never be translated.
_SKIP_TEXT_TAGS = {"script", "style"}


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"[warn] cannot parse {path}: {exc}")
        return default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_translator(from_lang: str, to_lang: str):
    """Return a callable str->str, or None if the engine/package is missing."""
    try:
        import argostranslate.translate as at
    except Exception as exc:
        print(f"[error] argostranslate not available: {exc}")
        return None
    try:
        languages = at.get_installed_languages()
        src = next((l for l in languages if l.code == from_lang), None)
        dst = next((l for l in languages if l.code == to_lang), None)
        if src is None or dst is None:
            print(f"[error] argos package {from_lang}->{to_lang} not installed")
            return None
        translation = src.get_translation(dst)
    except Exception as exc:
        print(f"[error] cannot init argos translation: {exc}")
        return None

    def _translate(text: str) -> str:
        if not text or not text.strip():
            return text
        try:
            return translation.translate(text)
        except Exception as exc:
            print(f"[warn] translation failed, keeping source: {exc}")
            return text

    return _translate


class _HTMLTextTranslator(HTMLParser):
    """Re-emit the HTML unchanged except for translated text nodes."""

    def __init__(self, translate):
        super().__init__(convert_charrefs=False)
        self._translate = translate
        self._out = []
        self._skip_depth = 0

    def result(self) -> str:
        return "".join(self._out)

    def handle_starttag(self, tag, attrs):
        self._out.append(self.get_starttag_text())
        if tag in _SKIP_TEXT_TAGS:
            self._skip_depth += 1

    def handle_startendtag(self, tag, attrs):
        self._out.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if tag in _SKIP_TEXT_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        self._out.append(f"</{tag}>")

    def handle_data(self, data):
        if self._skip_depth > 0 or not data.strip():
            self._out.append(data)
            return
        leading = data[: len(data) - len(data.lstrip())]
        trailing = data[len(data.rstrip()):]
        core = data.strip()
        try:
            translated = self._translate(core)
        except Exception as exc:
            print(f"[warn] text node translation failed: {exc}")
            translated = core
        self._out.append(f"{leading}{translated}{trailing}")

    def handle_entityref(self, name):
        self._out.append(f"&{name};")

    def handle_charref(self, name):
        self._out.append(f"&#{name};")

    def handle_comment(self, data):
        self._out.append(f"<!--{data}-->")

    def handle_decl(self, decl):
        self._out.append(f"<!{decl}>")


def translate_html(html_str: str, translate) -> str:
    parser = _HTMLTextTranslator(translate)
    parser.feed(html_str)
    parser.close()
    return parser.result()


def translate_products_file(src_path: Path, dst_path: Path, translate,
                            cache: dict, force: bool) -> bool:
    data = load_json(src_path)
    if data is None:
        return False
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True)
    h = source_hash(raw)
    cache_key = str(dst_path.relative_to(DATA_DIR))
    if not force and cache.get(cache_key) == h and dst_path.exists():
        print(f"  [skip] {cache_key} (unchanged)")
        return False

    out = dict(data)
    products = []
    for product in data.get("products", []):
        p = dict(product)
        title = p.get("title")
        if title:
            try:
                p["title"] = translate(title)
            except Exception as exc:
                print(f"  [warn] title translation failed for "
                      f"{p.get('product_id', '?')}: {exc}")
        products.append(p)
    out["products"] = products
    write_json(dst_path, out)
    cache[cache_key] = h
    print(f"  [ok] {cache_key} ({len(products)} products)")
    return True


def translate_blog_file(src_path: Path, dst_path: Path, lang: str, translate,
                        cache: dict, force: bool) -> bool:
    data = load_json(src_path)
    if data is None:
        return False
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True)
    h = source_hash(raw)
    cache_key = str(dst_path.relative_to(DATA_DIR))
    if not force and cache.get(cache_key) == h and dst_path.exists():
        print(f"  [skip] {cache_key} (unchanged)")
        return False

    out = dict(data)
    out["lang"] = lang
    if out.get("title"):
        try:
            out["title"] = translate(out["title"])
        except Exception as exc:
            print(f"  [warn] blog title translation failed: {exc}")
    for desc_key in ("meta_desc", "meta_description"):
        if out.get(desc_key):
            try:
                out[desc_key] = translate(out[desc_key])
            except Exception as exc:
                print(f"  [warn] {desc_key} translation failed: {exc}")
    if out.get("content_html"):
        try:
            out["content_html"] = translate_html(out["content_html"], translate)
        except Exception as exc:
            print(f"  [warn] content_html translation failed, keeping source: {exc}")
    write_json(dst_path, out)
    cache[cache_key] = h
    print(f"  [ok] {cache_key}")
    return True


def iter_product_sources():
    src_root = DATA_DIR / "products" / SOURCE_LANG
    if src_root.exists():
        for f in sorted(src_root.glob("*.json")):
            yield f, f.name, ""
        article_dir = src_root / "_article"
        if article_dir.exists():
            for f in sorted(article_dir.glob("*.json")):
                yield f, f.name, "_article"


def run(lang: str, force: bool) -> int:
    if lang == SOURCE_LANG:
        print(f"[translate] nothing to do for source language '{lang}'")
        return 0

    translate = get_translator(SOURCE_LANG, lang)
    if translate is None:
        print("[translate] translator unavailable, leaving translations untouched")
        return 1

    cache = load_json(CACHE_PATH, default={}) or {}
    changed = 0

    print(f"[translate] products en -> {lang}")
    for src_path, name, sub in iter_product_sources():
        dst_path = DATA_DIR / "products" / lang / sub / name if sub \
            else DATA_DIR / "products" / lang / name
        try:
            if translate_products_file(src_path, dst_path, translate, cache, force):
                changed += 1
        except Exception as exc:
            print(f"  [warn] failed {name}: {exc}")

    print(f"[translate] blog en -> {lang}")
    blog_src = DATA_DIR / "blog" / SOURCE_LANG
    if blog_src.exists():
        for src_path in sorted(blog_src.glob("*.json")):
            dst_path = DATA_DIR / "blog" / lang / src_path.name
            try:
                if translate_blog_file(src_path, dst_path, lang, translate, cache, force):
                    changed += 1
            except Exception as exc:
                print(f"  [warn] failed {src_path.name}: {exc}")

    write_json(CACHE_PATH, cache)
    print(f"[translate] done: {changed} file(s) (re)translated")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Translate EN content to a target language.")
    parser.add_argument("--lang", default="it", help="target language code (default: it)")
    parser.add_argument("--force", action="store_true", help="ignore cache and re-translate all")
    args = parser.parse_args()
    sys.exit(run(args.lang, args.force))


if __name__ == "__main__":
    main()
