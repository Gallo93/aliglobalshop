"""Generate one SEO blog article via Anthropic API and save JSON in _data/blog/en/.

Reads next unused topic from _data/blog-calendar-en.json, marks it used after success.
When all topics are used, resets the calendar and starts over.
"""
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import anthropic

BASE_DIR = Path(__file__).parent.parent
BLOG_DIR = BASE_DIR / "_data" / "blog" / "en"
CALENDAR_PATH = BASE_DIR / "_data" / "blog-calendar-en.json"
CONFIG_PATH = BASE_DIR / "_data" / "config.json"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# Quante volte ritentare API + parse JSON su uno stesso topic prima di arrendersi.
# La malformazione JSON e' stocastica: un re-roll quasi sempre produce JSON valido.
MAX_RETRIES = 3

# Tetto di token in output: deve coprire articolo 1000-1200 parole + wrapper JSON.
# A 3500 la risposta veniva troncata -> JSON non chiuso/invalido. 8000 da' margine.
MAX_TOKENS = 8000

# Exit codes
EXIT_API_ERROR = 3
EXIT_INVALID_JSON = 4
EXIT_NO_CREDIT = 5

PROMPT = """You are an expert SEO copywriter for aliglobalshop.com, an AliExpress affiliate site.
CURRENT YEAR: {year}
KEYWORD TARGET: {primary_keyword}
SEARCH INTENT: {intent}
CATEGORY: {category}
CATEGORY URL: {category_url}

Write a complete blog article in valid HTML (body content only, no <html>/<head>/<body> tags).

STRICT REQUIREMENTS:
- title: max 43 chars (the page template adds " | AliGlobalShop" making it 60 total), must include primary keyword and current year ({year})
- meta_desc: max 155 chars, must include primary keyword
- slug: lowercase hyphens only, max 60 chars, ASCII, include primary keyword and year
- lang: "en"
- category: match the CATEGORY field above
- NEVER use em-dashes (—). Use commas, colons, or rephrase instead.

LENGTH AND FORMATTING:
- Target 1000 to 1200 words of body content. Do not pad to reach the count, cut anything that repeats.
- Break up long sections: use <h3> subheadings and <ul>/<ol> bullet lists wherever you compare options, list features, or give steps. No wall-of-text sections.
- Exactly one section <h2> must include the keyword "{primary_keyword}", written naturally and in proper title case (NOT lowercase, NOT crammed mid-sentence). Always capitalize the brand correctly as "AliExpress" (never "aliexpress"). Phrase the heading so the keyword reads as a natural part of it. The other <h2> headings use natural variants.

CONTENT STRUCTURE (use this order):
1. <h1> matching title, includes primary keyword
2. Intro paragraph (80-120 words): hook + pain point + promise. Open with a concrete, specific angle for THIS topic (a scenario, a number, a question). Do NOT open with a generic budget cliche.
3. <h2> first section heading: it must NOT repeat or paraphrase the article title/H1. Open a concrete sub-topic instead (buying criteria, what to know before you buy, useful context). One of the H2s contains the keyword per the rule above, but the FIRST H2 must not be a restatement of the title.
4. 2-4 sections of paragraphs (120-180 words each) plus <h3> + <ul>/<ol> where it helps, with practical tips, comparisons, buying advice
5. Include 1-2 internal links to the category page: <a href="{category_url}">browse all {category} deals</a>
6. <h2> FAQ heading uses conversational language (e.g. "Common Questions Answered"), not the exact keyword
7. FAQ section: wrap in <div class="faq"> and use <details><summary>Question?</summary><p>Answer (2-3 sentences).</p></details> for EACH question. Minimum 3 questions.
8. <h2> conclusion heading: write a fresh, specific heading for THIS article. Do NOT use "Final Verdict", "Is It Worth It in {year}", or any cloned title of that shape.
9. Conclusion paragraph (60-80 words)

BANNED PHRASES (do not use these or close paraphrases, they recur in every article and must stop):
- "should not drain your wallet", "should not cost a fortune", "won't break the bank"
- "This guide breaks down", "In this guide", "this comprehensive guide"
- "Final Verdict", "Is It Worth It in {year}"
Vary the opening sentence and every section heading so two articles never read the same.

SEO RULES — FOLLOW EXACTLY:
- The EXACT phrase "{primary_keyword}" must appear AT MOST 3 times in the entire article (title + all headings + all body text combined). Count carefully before outputting.
- For every additional mention beyond those 3, use a natural synonym or variant instead (examples: for "aliexpress smart bulbs" use "these WiFi bulbs", "smart lighting options", "color-changing LEDs"; for "robot vacuum" use "the cleaner", "this model", "automated cleaning").
- ONLY ONE H2 heading may contain the keyword, and it must read naturally with proper title case and the brand spelled "AliExpress" (never lowercase, never forced mid-sentence). All other H2 headings must use natural language variants.
- Never repeat the same sentence structure or idea in different words just to fill space. Every sentence must add new, useful information.
- All external links to AliExpress must have rel="nofollow sponsored"
- Use specific numbers, prices (in USD, with the $ symbol), and years ({year}) to increase CTR
- Do NOT mention any competitor sites (Amazon, eBay, Temu, etc.)
- Do NOT add an affiliate disclosure or disclaimer paragraph: the page template adds it automatically.
- NEVER use em-dashes (—) anywhere in the article. Use commas, colons, periods, or rephrase instead.

OUTPUT FORMAT: respond ONLY with valid JSON (no markdown, no code fences):
{{
  "title": "...",
  "slug": "...",
  "date": "...",
  "content_html": "<h1>...</h1><p>...</p>...",
  "lang": "en",
  "meta_desc": "...",
  "category": "...",
  "primary_keyword": "{primary_keyword}"
}}"""


def load_calendar() -> list:
    if not CALENDAR_PATH.exists():
        print(f"[blog] missing calendar at {CALENDAR_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(CALENDAR_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_calendar(items: list) -> None:
    with open(CALENDAR_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def active_boost_niches() -> list:
    """Nicchie da prioritizzare se il boost niche_boost e' attivo OGGI.

    Lettura difensiva di config.json: qualsiasi errore (file assente, JSON
    rotto, data malformata, boost scaduto) -> [] = nessun boost, comportamento
    sequenziale invariato.
    """
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        boost = cfg.get("niche_boost") or {}
        until = date.fromisoformat(boost["until"])
        niches = boost.get("niches") or []
        if date.today() < until and niches:
            return list(niches)
    except Exception:
        pass
    return []


def pick_next_topic(items: list):
    """Primo topic non-usato.

    Mentre il boost e' attivo (oggi < niche_boost.until) prova prima i topic
    non-usati la cui category e' tra le nicchie in boost, nell'ordine dato.
    Se non ne trova (o boost inattivo/scaduto) fa fallback alla scansione
    sequenziale invariata.
    """
    boost_niches = active_boost_niches()
    for niche in boost_niches:
        for i, item in enumerate(items):
            if not item.get("used") and item.get("category") == niche:
                return i, item
    for i, item in enumerate(items):
        if not item.get("used"):
            return i, item
    return None, None


def iter_unused_topics(items: list, start_idx: int):
    """Yield (idx, topic) for every unused topic from start_idx onward."""
    for i in range(start_idx, len(items)):
        if not items[i].get("used"):
            yield i, items[i]


def reset_calendar(items: list) -> list:
    """Mark all topics unused so the cycle restarts."""
    for item in items:
        item["used"] = False
        item.pop("used_at", None)
    return items


def strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```$", "", text)
    return text.strip()


def _is_credit_error(exc: Exception) -> bool:
    """True se l'errore indica credito Anthropic esaurito/insufficiente."""
    text = str(exc).lower()
    if "credit balance is too low" in text or "insufficient" in text:
        return True
    status = getattr(exc, "status_code", None)
    return status in (402,)


def call_anthropic(prompt: str) -> str:
    if not ANTHROPIC_API_KEY:
        print("[blog] missing ANTHROPIC_API_KEY", file=sys.stderr)
        sys.exit(2)
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    try:
        msg = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        if _is_credit_error(exc):
            print(
                "[blog] CREDITO ANTHROPIC ESAURITO - ricaricare su "
                "console.anthropic.com (nessun articolo generato).",
                file=sys.stderr,
            )
            sys.exit(EXIT_NO_CREDIT)
        print(f"[blog] chiamata Anthropic fallita ({type(exc).__name__}): {exc}", file=sys.stderr)
        sys.exit(EXIT_API_ERROR)
    return "".join(
        block.text for block in msg.content if getattr(block, "type", "") == "text"
    )


def generate_for_topic(topic: dict, year: int):
    """Genera e fa il parse dell'articolo per UN topic, con retry sul JSON malformato.

    Ritenta la chiamata API + parse fino a MAX_RETRIES volte: poiche' la
    malformazione JSON e' stocastica, un re-roll quasi sempre produce JSON valido.
    Usa json.loads(strict=False) per tollerare control char nelle stringhe.
    Ritorna il dict articolo al primo parse valido, None se esauriti i tentativi.
    Gli errori di credito/API restano gestiti da call_anthropic (exit 5/3).
    """
    cat_slug = topic.get("category", "").lower().replace(" ", "-")
    prompt = PROMPT.format(
        year=year,
        primary_keyword=topic["primary_keyword"],
        intent=topic.get("intent", "informational"),
        category=topic.get("category", ""),
        category_url=f"/en/{cat_slug}/",
    )
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"[blog] '{topic['topic']}' tentativo {attempt}/{MAX_RETRIES}")
        raw = strip_code_fences(call_anthropic(prompt))
        try:
            return json.loads(raw, strict=False)
        except json.JSONDecodeError as exc:
            print(f"[blog] JSON non valido (tentativo {attempt}/{MAX_RETRIES}): {exc}", file=sys.stderr)
            print(raw[:500], file=sys.stderr)
    print(f"[blog] esauriti i {MAX_RETRIES} tentativi per '{topic['topic']}'.", file=sys.stderr)
    return None


def slugify(text: str, limit: int = 60) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text[:limit].rstrip("-") or "article"


def slug_exists(slug: str) -> bool:
    """True se esiste già un articolo con questo slug, a prescindere dalla data nel filename."""
    if not BLOG_DIR.exists():
        return False
    for path in BLOG_DIR.glob("*.json"):
        try:
            with open(path, encoding="utf-8") as f:
                if json.load(f).get("slug") == slug:
                    return True
        except (json.JSONDecodeError, OSError):
            continue
    return False


# Parole da rimuovere quando si normalizza un topic a chiave canonica: brand,
# anni, e i filler/suffissi SEO che generano quasi-gemelle ("guide", "top picks",
# "best buys", ...). Senza di questi resta il nucleo di sostantivi del topic, cosi
# "aliexpress travel gadgets 2026 guide" e "aliexpress travel gadgets 2026 top picks"
# collassano sulla stessa chiave. NB: "smart", "wireless", ecc. NON sono filler:
# distinguono prodotti diversi (smart plug vs plug) e vanno tenuti.
_TOPIC_STOPWORDS = frozenset({
    "aliexpress",
    "guide", "guides", "top", "picks", "pick", "best", "buys", "buy", "best-buys",
    "buyer", "buyers", "review", "reviews", "tips", "tip", "ideas", "idea", "list",
    "roundup", "that", "work", "works", "you", "need", "under", "the", "your",
    "for", "to", "of", "a", "an", "on", "in", "with", "vs", "and", "or", "is",
})

# Token tutto-cifre o anno -> scartati (2025, 2026, 50, 20, ...).
_NUM_RE = re.compile(r"^\d+$")


def _topic_key(text: str) -> str:
    """Chiave canonica di un topic: lowercase, via brand/anni/numeri/filler SEO,
    nucleo di sostantivi ordinato alfabeticamente e joinato con spazio.

    Robusta per costruzione:
    - input None/vuoto -> "".
    - se dopo lo stripping non resta nulla (topic tutto-filler, es. "best 2026
      guide") FALLBACK alla stringa normalizzata intera (token non-stopword
      assenti -> si tiene tutto tranne numeri), cosi la chiave non e' mai vuota
      e due topic diversi non collassano per sbaglio su "".
    """
    if not text:
        return ""
    norm = re.sub(r"[^a-z0-9\s-]", " ", text.lower())
    tokens = [t for t in re.split(r"[\s_-]+", norm) if t]
    core = [t for t in tokens if t not in _TOPIC_STOPWORDS and not _NUM_RE.match(t)]
    if not core:
        # tutto filler/numeri: fallback ai token non-numerici (incl. stopword),
        # mai vuoto se c'era almeno una parola.
        core = [t for t in tokens if not _NUM_RE.match(t)] or tokens
    return " ".join(sorted(set(core)))


def _article_topic_key(data: dict) -> str:
    """Topic-key di un articolo gia' pubblicato. Preferisce primary_keyword
    (campo piu pulito), poi slug, poi title."""
    return _topic_key(
        data.get("primary_keyword") or data.get("slug") or data.get("title", "")
    )


def published_topic_keys() -> set:
    """Set delle topic-key di TUTTI gli articoli EN gia' pubblicati.

    Difensiva: file illeggibili/non-JSON saltati. Gli stub redirect_to NON
    vengono esclusi di proposito: rappresentano un topic gia' coperto, quindi
    la loro chiave deve continuare a bloccare i rigeneri."""
    keys = set()
    if not BLOG_DIR.exists():
        return keys
    for path in BLOG_DIR.glob("*.json"):
        try:
            with open(path, encoding="utf-8") as f:
                key = _article_topic_key(json.load(f))
            if key:
                keys.add(key)
        except (json.JSONDecodeError, OSError):
            continue
    return keys


def topic_key_for_item(item: dict) -> str:
    """Topic-key di un topic di calendario (primary_keyword, poi topic/title)."""
    return _topic_key(item.get("primary_keyword") or item.get("topic", ""))


def prune_calendar_duplicates(items: list) -> int:
    """Rimuove dai topic ANCORA IN CODA (unused) quelli la cui topic-key collide
    con un articolo gia' pubblicato, cosi non rigenerano doppioni a slug diverso.
    I topic gia' used restano (sono lo storico). Ritorna quanti ne ha rimossi.

    Tutto in try/except: qualunque errore -> nessuna rimozione, calendario intatto.
    """
    try:
        published = published_topic_keys()
        if not published:
            return 0
        kept, removed = [], 0
        for item in items:
            if not item.get("used") and topic_key_for_item(item) in published:
                removed += 1
                print(f"[blog] [prune] topic-doppione rimosso dalla coda: {item.get('topic')!r}")
                continue
            kept.append(item)
        if removed:
            items[:] = kept
        return removed
    except Exception as exc:  # noqa: BLE001 - fallback prudente, mai bloccare
        print(f"[blog] prune_calendar_duplicates saltata ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 0


def main() -> None:
    items = load_calendar()

    # Pulizia: togli dalla coda i topic la cui chiave canonica coincide con un
    # articolo gia' pubblicato (sotto qualsiasi slug). Previene la rigenerazione
    # di quasi-gemelle. No-op se la coda e' gia' pulita.
    pruned = prune_calendar_duplicates(items)
    if pruned:
        save_calendar(items)
        print(f"[blog] [prune] {pruned} topic-doppione rimossi dal calendario.")

    # Set di topic-key gia' coperte: articoli pubblicati + topic scelti in
    # questo stesso run. Difensivo: se la scansione fallisce, set vuoto = guard
    # inattivo, pipeline come prima.
    try:
        seen_topic_keys = published_topic_keys()
    except Exception:  # noqa: BLE001
        seen_topic_keys = set()

    idx, topic = pick_next_topic(items)

    if topic is None:
        print("[blog] all topics used. Resetting calendar for next cycle.")
        items = reset_calendar(items)
        save_calendar(items)
        idx, topic = pick_next_topic(items)

    if topic is None:
        print("[blog] calendar is empty, nothing to do.", file=sys.stderr)
        sys.exit(1)

    current_year = date.today().year
    today = date.today().isoformat()

    # Unico loop coerente sui topic non-usati. Per ciascuno:
    # - JSON invalido dopo i retry -> NON marca used (ritentabile), avanza;
    # - slug gia' presente -> marca used+used_at, logga lo skip e CONTINUA
    #   (non spreca il run su un duplicato);
    # - articolo nuovo salvato -> marca used+used_at e termina (return).
    for idx, topic in iter_unused_topics(items, idx):
        # Guard topic-level PRIMA della chiamata API: se un articolo con la stessa
        # chiave canonica esiste gia' (anche sotto slug diverso) o e' gia' stato
        # scelto in questo run, salta senza spendere crediti. Stessa semantica di
        # slug_exists: marca used+used_at, logga, continua. Difensivo: chiave vuota
        # (parsing degenere) -> non blocca, prosegue come oggi.
        tkey = topic_key_for_item(topic)
        if tkey and tkey in seen_topic_keys:
            print(f"[blog] [skip] topic-key gia' coperta ({tkey!r}): {topic['topic']!r}")
            items[idx]["used"] = True
            items[idx]["used_at"] = today
            save_calendar(items)
            print(f"[blog] topic #{idx} marcato used (topic-doppione), avanzo al successivo.")
            continue

        print(f"[blog] generating article for: {topic['topic']} (year={current_year})")
        article = generate_for_topic(topic, current_year)

        if article is None:
            print(f"[blog] topic #{idx} fallito (JSON), avanzo al successivo.", file=sys.stderr)
            continue

        slug = slugify(article.get("slug") or article.get("title", ""))
        article["slug"] = slug

        if slug_exists(slug):
            print(f"[blog] [skip] slug already present: {slug}")
            items[idx]["used"] = True
            items[idx]["used_at"] = today
            save_calendar(items)
            print(f"[blog] topic #{idx} marcato used (duplicato), avanzo al successivo.")
            continue

        article["date"] = today
        article.setdefault("category", topic.get("category", ""))
        article.setdefault("primary_keyword", topic["primary_keyword"])

        BLOG_DIR.mkdir(parents=True, exist_ok=True)
        out_path = BLOG_DIR / f"{today}-{slug}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(article, f, ensure_ascii=False, indent=2)
        print(f"[blog] saved: {out_path.relative_to(BASE_DIR)}")

        if tkey:
            seen_topic_keys.add(tkey)
        items[idx]["used"] = True
        items[idx]["used_at"] = today
        save_calendar(items)
        print(f"[blog] calendar updated. Marked topic #{idx} as used.")
        return

    print(
        "[blog] nessun articolo nuovo prodotto: tutti i topic non-usati erano "
        "duplicati (slug gia' presente) o hanno fallito il parse JSON dopo "
        f"{MAX_RETRIES} tentativi.",
        file=sys.stderr,
    )
    sys.exit(EXIT_INVALID_JSON)


if __name__ == "__main__":
    main()
