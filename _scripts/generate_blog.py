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
- At least one section <h2> must contain the exact phrase "{primary_keyword}" (or a tight variant that keeps every keyword word). The other <h2> headings use natural variants.

CONTENT STRUCTURE (use this order):
1. <h1> matching title, includes primary keyword
2. Intro paragraph (80-120 words): hook + pain point + promise. Open with a concrete, specific angle for THIS topic (a scenario, a number, a question). Do NOT open with a generic budget cliche.
3. <h2> a section heading (one of the H2s contains the keyword per the rule above)
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
- ONLY ONE H2 heading may contain the exact keyword phrase. All other H2 headings must use natural language variants.
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


def pick_next_topic(items: list):
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


def main() -> None:
    items = load_calendar()
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
