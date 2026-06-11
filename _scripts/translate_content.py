"""
Translate EN content to a target language (default IT).

Sources translated:
  1. _data/products/<lang>/*.json   <- _data/products/en/*.json
     (field: title; prices converted to the target-language currency)
     including the _article/*.json sub-folder. ALWAYS via Argos Translate.
  2. _data/blog/<lang>/*.json        <- _data/blog/en/*.json
     (fields: title, meta_desc / meta_description, content_html). By default
     via the Anthropic API (claude, native-quality copy: full heading
     translation, correct tech terms, HTML/price tokens preserved verbatim);
     set BLOG_TRANSLATOR=argos to fall back to the Argos HTML-text path.
     The Claude path needs ANTHROPIC_API_KEY (model override ANTHROPIC_MODEL,
     default claude-sonnet-4-6); on any API/parse error it logs and keeps the
     EN source for that article instead of crashing the run.

Prices: products keep their structure but price / original_price /
price_history[].price are converted from the EN source currency (USD) to the
target-language currency read from _data/i18n/<lang>.json (_meta.currency),
using an exchange rate from _data/config.json ("fx_rates": {"EUR": 0.92, ...}),
overridable per run via the env var FX_RATE_<CUR> (e.g. FX_RATE_EUR). When the
target currency equals the source currency, prices are copied unchanged.

Why rate conversion and not a second EUR fetch: the AliExpress affiliate API
does support a target_currency parameter (fetch_products.py already sends
target_currency=USD), so an EUR fetch is technically possible. We deliberately
convert the existing USD data instead, because (a) a second fetch would double
the API calls and Cloudinary uploads, and (b) reusing the same EN JSON keeps
the IT product set aligned 1:1 with EN (identical product_id / slug), which the
per-language build relies on. The static rate is a pragmatic default that
ages over time, so it is intentionally overridable via config.json "fx_rates"
and the FX_RATE_<CUR> env var and can be refreshed without code changes.

Internal site links inside blog content_html are repointed from /en/ to the
target language: an href starting with "/en/" or "<site_url>/en/" becomes
"/<lang>/" / "<site_url>/<lang>/". External links and any href that does not
start with one of those internal prefixes are left untouched. Deterministic,
idempotent (a "/it/" link is not matched again).

URLs, slugs, product ids and image URLs are never touched. Slugs stay
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
import html
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "_data"
CONFIG_PATH = DATA_DIR / "config.json"
I18N_DIR = DATA_DIR / "i18n"
CACHE_PATH = DATA_DIR / ".translate_cache.json"

SOURCE_LANG = "en"

# Tags whose text content must never be translated.
_SKIP_TEXT_TAGS = {"script", "style"}

# Fallback exchange rates (1 source-currency unit -> target currency) used only
# when config.json has no "fx_rates" entry and no FX_RATE_<CUR> env override.
# Static defaults age over time: prefer config.json "fx_rates" / FX_RATE_<CUR>
# to keep them current (see module docstring for why conversion over re-fetch).
_DEFAULT_FX_RATES = {"EUR": 0.92}

# Per-language override for tech terms Argos mistranslates in short titles
# (e.g. "earbuds" -> "earbudi", "smart bulbs" -> garbage). Applied after the
# machine translation as a whole-word, case-insensitive replacement. Keys are
# matched against the post-translation text; longer phrases first so multi-word
# terms win over their single-word substrings.
_TITLE_GLOSSARY = {
    "it": {
        "smart bulbs": "lampadine smart",
        "smart bulb": "lampadina smart",
        "smart home": "casa intelligente",
        "home gym": "palestra in casa",
        "power bank": "power bank",
        "earbuds": "auricolari",
        "earbudi": "auricolari",
        "smartwatches": "smartwatch",
        "smartwatch": "smartwatch",
        "yoga gear": "attrezzatura yoga",
        "travel gadgets": "gadget da viaggio",
        "bike accessories": "accessori bici",
        "robot vacuum": "robot aspirapolvere",
        "coupon codes": "codici coupon",
    },
    "es": {
        "smart bulbs": "bombillas inteligentes",
        "smart bulb": "bombilla inteligente",
        "smart home": "hogar inteligente",
        "home gym": "gimnasio en casa",
        "power bank": "power bank",
        "earbuds": "auriculares",
        "discos inalámbricos": "auriculares inalámbricos",
        "smartwatches": "smartwatches",
        "smartwatch": "smartwatch",
        "yoga gear": "equipo de yoga",
        "travel gadgets": "gadgets de viaje",
        "bike accessories": "accesorios de bici",
        "robot vacuum": "robot aspirador",
        "coupon codes": "códigos de cupón",
    },
    "de": {
        "smart bulbs": "smarte Glühbirnen",
        "smart bulb": "smarte Glühbirne",
        "smart home": "Smart Home",
        "home gym": "Heim-Fitnessstudio",
        "power bank": "Powerbank",
        "earbuds": "Earbuds",
        "smartwatches": "Smartwatches",
        "smartwatch": "Smartwatch",
        "yoga gear": "Yoga-Ausrüstung",
        "travel gadgets": "Reise-Gadgets",
        "bike accessories": "Fahrrad-Zubehör",
        "robot vacuum": "Saugroboter",
        "coupon codes": "Gutschein-Codes",
    },
    "fr": {
        "smart bulbs": "ampoules connectées",
        "smart bulb": "ampoule connectée",
        "smart home": "maison connectée",
        "home gym": "salle de sport à domicile",
        "power bank": "batterie externe",
        "earbuds": "écouteurs sans fil",
        "wireless earbuds": "écouteurs sans fil",
        "smartwatches": "montres connectées",
        "smartwatch": "montre connectée",
        "yoga gear": "équipement de yoga",
        "travel gadgets": "gadgets de voyage",
        "bike accessories": "accessoires de vélo",
        "robot vacuum": "aspirateur robot",
        "coupon codes": "codes coupon",
    },
}

# Currency symbols per target currency, used to normalize a stray source "$"
# left in a translated title to the target currency symbol. Blog titles store
# raw UTF-8 (matching Argos output), so we use the literal symbol.
_CURRENCY_SYMBOLS = {"EUR": "€"}


def apply_title_glossary(text: str, lang: str, target_currency: str) -> str:
    """Post-process a machine-translated title: fix tech terms via the per-lang
    glossary and replace a stray source '$' with the target currency symbol."""
    if not text:
        return text
    glossary = _TITLE_GLOSSARY.get(lang, {})
    for term in sorted(glossary, key=len, reverse=True):
        text = re.sub(
            r'(?<![\w&])' + re.escape(term) + r'(?![\w;])',
            glossary[term], text, flags=re.IGNORECASE,
        )
    sym = _CURRENCY_SYMBOLS.get(target_currency)
    if sym:
        text = text.replace("$", sym)
    return text


# --- Claude blog translation -------------------------------------------------
# Blog articles (and ONLY blog articles) are translated with the Anthropic API
# for native-quality copy: products stay on Argos (translate_products_file).
# Toggle via BLOG_TRANSLATOR=claude|argos (default claude). The Claude path
# needs ANTHROPIC_API_KEY; if it is missing or the call fails, translate_blog_*
# falls back to keeping the EN source rather than crashing the run.

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

_LANG_NAMES = {
    "it": "Italian",
    "es": "Spanish",
    "de": "German",
    "fr": "French",
}

_BLOG_TRANSLATE_PROMPT = """You are a native {lang_name} translator and SEO copy editor for an AliExpress affiliate blog.
Translate the JSON article below from English into natural, fluent {lang_name}. Output {lang_name} that reads as if written by a native speaker, never a literal machine translation.

TRANSLATE FULLY (no English left behind):
- The title and EVERY heading (h1/h2/h3). Do not leave English headings such as "Best Buys", "Top Picks", "Smart Gear Worth Packing", "Home Gym", "Final Verdict", "Common Questions Answered". Translate them all.
- Use the correct {lang_name} tech terms. Examples: earbuds, rowing machine, "rows" (the exercise), dumbbells, plugs (electrical sockets), hub, barbell, cable machine. Pick the term a {lang_name} native shopper would actually use. Never invent absurd words.

PRESERVE EXACTLY (copy verbatim, do not translate or alter):
- All HTML structure: every tag, attribute, class and value (e.g. <div class="faq">, <details><summary>, <a href="...">, <ul>, <h2>). Keep the same tags in the same order.
- Every price token written with the $ symbol and USD digits, e.g. "$8", "$3 to $7", "$19.99". Leave the $ and the numbers untouched. A separate build step converts them to euros.
- URLs, hrefs, src and any slug.

RULES:
- Do NOT use em-dashes (—). Use commas, colons, parentheses or rephrase.
- Keep the title concise: at most ~50 characters, natural in {lang_name}.
- Keep meta_desc at most 155 characters, natural and sensible in {lang_name}.
- Do not add, remove or reorder HTML elements. Translate only the human-readable text inside them.

OUTPUT: respond ONLY with a single valid JSON object (no markdown, no code fences) with exactly these keys, each holding the translated {lang_name} value:
{{"title": "...", "meta_desc": "...", "content_html": "..."}}

ARTICLE TO TRANSLATE (JSON):
{payload}"""


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```$", "", text)
    return text.strip()


def get_claude_blog_translator(lang: str):
    """Return a callable(title, meta_desc, content_html) -> dict for the blog,
    or None if the Anthropic SDK / key is missing. The callable raises on a
    failed API call so the caller can fall back to the EN source per article."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("[error] ANTHROPIC_API_KEY missing, cannot use Claude blog translator")
        return None
    try:
        import anthropic
    except Exception as exc:
        print(f"[error] anthropic SDK not available: {exc}")
        return None
    lang_name = _LANG_NAMES.get(lang, lang)
    client = anthropic.Anthropic(api_key=api_key)

    def _translate_article(title: str, meta_desc: str, content_html: str) -> dict:
        payload = json.dumps(
            {"title": title or "", "meta_desc": meta_desc or "",
             "content_html": content_html or ""},
            ensure_ascii=False,
        )
        prompt = _BLOG_TRANSLATE_PROMPT.format(lang_name=lang_name, payload=payload)
        msg = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "".join(
            block.text for block in msg.content
            if getattr(block, "type", "") == "text"
        )
        return json.loads(_strip_code_fences(raw))

    return _translate_article


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


def currency_for_lang(lang: str) -> str:
    return (load_json(I18N_DIR / f"{lang}.json", default={}) or {}).get(
        "_meta", {}).get("currency", "")


def resolve_fx_rate(config: dict, target_currency: str):
    """Rate to multiply a source-currency price by. None disables conversion."""
    if not target_currency:
        return None
    env_key = f"FX_RATE_{target_currency.upper()}"
    if os.getenv(env_key):
        try:
            return float(os.getenv(env_key))
        except (TypeError, ValueError):
            print(f"[warn] invalid {env_key}, ignoring")
    rates = config.get("fx_rates", {}) or {}
    if target_currency in rates:
        try:
            return float(rates[target_currency])
        except (TypeError, ValueError):
            print(f"[warn] invalid fx_rates[{target_currency}], ignoring")
    return _DEFAULT_FX_RATES.get(target_currency)


def convert_price(value, rate: float):
    """Convert a numeric-ish price by rate, preserving non-numeric values."""
    if value is None or value == "":
        return value
    try:
        converted = round(float(str(value).replace(",", "").strip()) * rate, 2)
    except (TypeError, ValueError):
        return value
    return converted


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


def rewrite_internal_href(href: str, lang: str, site_url: str) -> str:
    """Repoint internal /en/ links to /<lang>/; leave everything else as-is."""
    if not href:
        return href
    src_prefix = f"/{SOURCE_LANG}/"
    dst_prefix = f"/{lang}/"
    if site_url:
        site_src = f"{site_url}{src_prefix}"
        if href.startswith(site_src):
            return f"{site_url}{dst_prefix}" + href[len(site_src):]
    if href.startswith(src_prefix):
        return dst_prefix + href[len(src_prefix):]
    return href


class _HTMLTextTranslator(HTMLParser):
    """Re-emit the HTML unchanged except for translated text nodes.

    For <a> tags the start tag is rebuilt from the parsed attrs so that an
    internal /en/ href can be repointed to /<lang>/; every other tag is
    re-emitted verbatim via get_starttag_text() to preserve markup exactly.
    """

    def __init__(self, translate, lang: str, site_url: str):
        super().__init__(convert_charrefs=False)
        self._translate = translate
        self._lang = lang
        self._site_url = site_url
        self._out = []
        self._skip_depth = 0

    def result(self) -> str:
        return "".join(self._out)

    def _emit_starttag(self, tag, attrs, self_closing: bool):
        if tag != "a":
            self._out.append(self.get_starttag_text())
            return
        parts = [f"<{tag}"]
        for name, value in attrs:
            if value is None:
                parts.append(f" {name}")
                continue
            if name == "href":
                value = rewrite_internal_href(value, self._lang, self._site_url)
            parts.append(f' {name}="{html.escape(value, quote=True)}"')
        parts.append("/>" if self_closing else ">")
        self._out.append("".join(parts))

    def handle_starttag(self, tag, attrs):
        self._emit_starttag(tag, attrs, self_closing=False)
        if tag in _SKIP_TEXT_TAGS:
            self._skip_depth += 1

    def handle_startendtag(self, tag, attrs):
        self._emit_starttag(tag, attrs, self_closing=True)

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


def translate_html(html_str: str, translate, lang: str, site_url: str) -> str:
    parser = _HTMLTextTranslator(translate, lang, site_url)
    parser.feed(html_str)
    parser.close()
    return parser.result()


def translate_products_file(src_path: Path, dst_path: Path, translate,
                            fx_rate, cache: dict, force: bool) -> bool:
    data = load_json(src_path)
    if data is None:
        return False
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True)
    h = source_hash(raw)
    cache_key = dst_path.relative_to(DATA_DIR).as_posix()
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
        if fx_rate is not None:
            try:
                p["price"] = convert_price(p.get("price"), fx_rate)
                p["original_price"] = convert_price(p.get("original_price"), fx_rate)
                history = p.get("price_history")
                if isinstance(history, list):
                    p["price_history"] = [
                        {**h, "price": convert_price(h.get("price"), fx_rate)}
                        if isinstance(h, dict) else h
                        for h in history
                    ]
            except Exception as exc:
                print(f"  [warn] price conversion failed for "
                      f"{p.get('product_id', '?')}: {exc}")
        products.append(p)
    out["products"] = products
    write_json(dst_path, out)
    cache[cache_key] = h
    print(f"  [ok] {cache_key} ({len(products)} products)")
    return True


def translate_blog_file(src_path: Path, dst_path: Path, lang: str, translate,
                        site_url: str, cache: dict, force: bool,
                        target_currency: str = "") -> bool:
    data = load_json(src_path)
    if data is None:
        return False
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True)
    h = source_hash(raw)
    cache_key = dst_path.relative_to(DATA_DIR).as_posix()
    if not force and cache.get(cache_key) == h and dst_path.exists():
        print(f"  [skip] {cache_key} (unchanged)")
        return False

    out = dict(data)
    out["lang"] = lang
    if out.get("title"):
        try:
            out["title"] = apply_title_glossary(
                translate(out["title"]), lang, target_currency)
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
            out["content_html"] = translate_html(out["content_html"], translate, lang, site_url)
        except Exception as exc:
            print(f"  [warn] content_html translation failed, keeping source: {exc}")
    write_json(dst_path, out)
    cache[cache_key] = h
    print(f"  [ok] {cache_key}")
    return True


def _rewrite_internal_links(content_html: str, lang: str, site_url: str) -> str:
    """Repoint internal /en/ hrefs to /<lang>/ without touching text nodes,
    by re-parsing the HTML with an identity text translator (the parser only
    rewrites <a href> via rewrite_internal_href)."""
    return translate_html(content_html, lambda t: t, lang, site_url)


def translate_blog_file_claude(src_path: Path, dst_path: Path, lang: str,
                               translate_article, site_url: str, cache: dict,
                               force: bool) -> bool:
    """Translate ONE blog article with Claude (native quality). Same cache
    contract as translate_blog_file. On API/parse error, log in clear and keep
    the EN source for this article instead of crashing the run."""
    data = load_json(src_path)
    if data is None:
        return False
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True)
    h = source_hash(raw)
    cache_key = dst_path.relative_to(DATA_DIR).as_posix()
    if not force and cache.get(cache_key) == h and dst_path.exists():
        print(f"  [skip] {cache_key} (unchanged)")
        return False

    out = dict(data)
    out["lang"] = lang
    desc_key = "meta_desc" if out.get("meta_desc") else "meta_description"
    try:
        result = translate_article(
            out.get("title", ""),
            out.get(desc_key, ""),
            out.get("content_html", ""),
        )
    except Exception as exc:
        print(f"  [warn] Claude translation failed for {cache_key}, keeping "
              f"EN source: {type(exc).__name__}: {exc}")
        return False

    if not isinstance(result, dict):
        print(f"  [warn] Claude returned non-dict for {cache_key}, keeping EN source")
        return False

    if result.get("title"):
        out["title"] = result["title"]
    if out.get(desc_key) and result.get("meta_desc"):
        out[desc_key] = result["meta_desc"]
    if out.get("content_html") and result.get("content_html"):
        translated_html = result["content_html"]
        try:
            translated_html = _rewrite_internal_links(translated_html, lang, site_url)
        except Exception as exc:
            print(f"  [warn] internal link rewrite failed for {cache_key}: {exc}")
        out["content_html"] = translated_html

    write_json(dst_path, out)
    cache[cache_key] = h
    print(f"  [ok] {cache_key} (claude)")
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

    config = load_json(CONFIG_PATH, default={}) or {}
    site_url = config.get("site_url", "").rstrip("/")

    source_currency = currency_for_lang(SOURCE_LANG)
    target_currency = currency_for_lang(lang)
    fx_rate = None
    if target_currency and target_currency != source_currency:
        fx_rate = resolve_fx_rate(config, target_currency)
        if fx_rate is None:
            print(f"[translate] no fx rate for {source_currency}->{target_currency}, "
                  f"keeping source prices")
        else:
            print(f"[translate] price conversion {source_currency}->{target_currency} "
                  f"@ {fx_rate}")

    # Products always use Argos. Blog articles use Claude by default
    # (BLOG_TRANSLATOR=claude|argos) for native-quality copy.
    blog_mode = os.getenv("BLOG_TRANSLATOR", "claude").strip().lower()

    translate = get_translator(SOURCE_LANG, lang)
    claude_blog = get_claude_blog_translator(lang) if blog_mode == "claude" else None
    if blog_mode == "claude" and claude_blog is None:
        print("[translate] Claude blog translator unavailable, "
              "falling back to Argos for blog")

    if translate is None and claude_blog is None:
        print("[translate] no translator available, leaving translations untouched")
        return 1

    cache = load_json(CACHE_PATH, default={}) or {}
    changed = 0

    print(f"[translate] products en -> {lang}")
    if translate is None:
        print("  [warn] Argos unavailable, skipping products")
    else:
        for src_path, name, sub in iter_product_sources():
            dst_path = DATA_DIR / "products" / lang / sub / name if sub \
                else DATA_DIR / "products" / lang / name
            try:
                if translate_products_file(src_path, dst_path, translate, fx_rate, cache, force):
                    changed += 1
            except Exception as exc:
                print(f"  [warn] failed {name}: {exc}")

    print(f"[translate] blog en -> {lang} ({'claude' if claude_blog else 'argos'})")
    blog_src = DATA_DIR / "blog" / SOURCE_LANG
    if blog_src.exists():
        for src_path in sorted(blog_src.glob("*.json")):
            dst_path = DATA_DIR / "blog" / lang / src_path.name
            try:
                if claude_blog is not None:
                    if translate_blog_file_claude(src_path, dst_path, lang,
                                                  claude_blog, site_url, cache, force):
                        changed += 1
                elif translate is not None:
                    if translate_blog_file(src_path, dst_path, lang, translate,
                                           site_url, cache, force, target_currency):
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
