"""
Genera articoli blog con Anthropic API e salva JSON in _data/blog/en/
2 articoli al giorno — usa claude-sonnet-4-20250514
"""
import json
import os
from datetime import date
from pathlib import Path

import anthropic

BASE_DIR = Path(__file__).parent.parent
BLOG_DIR = BASE_DIR / "_data" / "blog" / "en"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-20250514"
ARTICLES_PER_DAY = 2


def generate_article(topic: str) -> dict:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": f"Write a short blog article about: {topic}"}],
    )
    return {
        "title": topic,
        "slug": topic.lower().replace(" ", "-"),
        "date": date.today().isoformat(),
        "content": message.content[0].text,
        "lang": "en",
    }


def main():
    topics = ["Best AliExpress gadgets 2025", "Top smart home deals"]
    for topic in topics[:ARTICLES_PER_DAY]:
        article = generate_article(topic)
        slug = article["slug"]
        today = article["date"]
        out_path = BLOG_DIR / f"{today}-{slug}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(article, f, ensure_ascii=False, indent=2)
        print(f"Articolo creato: {out_path.name}")


if __name__ == "__main__":
    main()
