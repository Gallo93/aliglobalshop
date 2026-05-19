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
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

AFFILIATE_DISCLAIMER = (
    '<p class="article-disclaimer">'
    '<em>Affiliate disclosure: AliGlobalShop earns a commission on qualifying purchases '
    'made through links on this page, at no extra cost to you. '
    'Prices and availability are subject to change — always check the product page for the current price. '
    'This article is for informational purposes only and does not constitute professional advice.'
    '</em></p>'
)

PROMPT = """You are an expert SEO copywriter for aliglobalshop.com, an AliExpress affiliate site.
KEYWORD TARGET: {primary_keyword}
SEARCH INTENT: {intent}
TONE: Friendly, practical, authoritative. Not salesy.

Write an article of 900-1200 words following these rules:
- Intro that answers the question immediately (no vague preamble)
- 3-5 H2 sections with practical tips or comparisons
- FAQ section with 3-5 Q&A
- Soft CTA at the end pointing readers to the relevant category on the site

STRICT CONTENT RULES — violations will cause rejection:
- NO invented statistics or percentages (e.g. "burns 40% more calories", "99% of users agree")
- NO medical or health claims (e.g. "improves sleep", "reduces joint pain", "boosts metabolism")
- NO specific price claims in the article body (prices change daily)
- NO fabricated user reviews or testimonials
- NO superlatives without factual backing ("world's best", "#1 rated")
- Keep claims conservative and verifiable

OUTPUT JSON only (no markdown fences, no commentary):
{{"title":"...","meta_desc":"...","slug":"...","content_html":"...","tags":[...],"category":"{category}","reading_time_min":N}}

Rules for output fields:
- title: max 60 chars, includes primary keyword
- meta_desc: max 155 chars, actionable
- slug: lowercase, hyphen-separated, max 60 chars, ASCII only
- content_html: valid HTML using only <h2> <h3> <p> <ul> <ol> <li> <strong> <em> tags
- reading_time_min: integer (words / 200)
"""


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


def call_anthropic(prompt: str) -> str:
    if not ANTHROPIC_API_KEY:
        print("[blog] missing ANTHROPIC_API_KEY", file=sys.stderr)
        sys.exit(2)
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    try:
        msg = client.messages.create(
            model=MODEL,
            max_tokens=3500,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        print(f"[blog] anthropic call failed: {exc}", file=sys.stderr)
        sys.exit(3)
    return "".join(
        block.text for block in msg.content if getattr(block, "type", "") == "text"
    )


def slugify(text: str, limit: int = 60) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text[:limit].rstrip("-") or "article"


def main() -> None:
    items = load_calendar()
    idx, topic = pick_next_topic(items)

    if topic is None:
        print("[blog] all topics used — resetting calendar for next cycle.")
        items = reset_calendar(items)
        save_calendar(items)
        idx, topic = pick_next_topic(items)

    if topic is None:
        print("[blog] calendar is empty — nothing to do.", file=sys.stderr)
        sys.exit(1)

    print(f"[blog] generating article for: {topic['topic']}")
    prompt = PROMPT.format(
        primary_keyword=topic["primary_keyword"],
        intent=topic.get("intent", "informational"),
        category=topic.get("category", ""),
    )
    raw = call_anthropic(prompt)
    raw = strip_code_fences(raw)

    try:
        article = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"[blog] invalid JSON from API: {exc}", file=sys.stderr)
        print(raw[:500], file=sys.stderr)
        sys.exit(4)

    # Append affiliate disclaimer to content
    content = article.get("content_html", "")
    article["content_html"] = content + "\n" + AFFILIATE_DISCLAIMER

    today = date.today().isoformat()
    slug = slugify(article.get("slug") or article.get("title", ""))
    article["slug"] = slug
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
    print(f"[blog] calendar updated — marked topic #{idx} as used.")


if __name__ == "__main__":
    main()
