"""
Strip the legacy hardcoded affiliate-disclosure block from EN blog articles.

Older EN articles embed the disclosure directly inside content_html as

    <p class="article-disclaimer"><em>Affiliate disclosure: ...</em></p>

The blog template now renders the disclosure on its own (bp_affiliate_disclosure
from i18n), so keeping the inline block produces a duplicate on EN and, because
the Claude backfill translates the EN source verbatim, on every translated
language too. This one-shot, idempotent cleaner removes that inline block from
the EN sources so the backfill yields clean translations.

Only the <p class="article-disclaimer">...</p> block (and a single immediately
preceding newline, if any) is removed; everything else in content_html is left
byte-for-byte intact. Running it again on an already-clean file is a no-op.

Usage:
    python _scripts/strip_legacy_disclaimer.py
"""
import json
import re
from pathlib import Path

BLOG_EN_DIR = Path(__file__).resolve().parent.parent / "_data" / "blog" / "en"

# Match an optional single leading newline followed by the disclaimer <p>.
# Non-greedy body, DOTALL so it spans any inner markup.
DISCLAIMER_RE = re.compile(
    r'\n?<p class="article-disclaimer">.*?</p>',
    re.DOTALL,
)


def strip_file(path: Path) -> bool:
    data = json.loads(path.read_text(encoding="utf-8"))
    html = data.get("content_html")
    if not isinstance(html, str):
        return False
    cleaned = DISCLAIMER_RE.sub("", html)
    if cleaned == html:
        return False
    data["content_html"] = cleaned
    # Match the existing on-disk format: 2-space indent, UTF-8, LF newlines,
    # no trailing newline -> only the disclaimer line changes in the diff.
    out = json.dumps(data, ensure_ascii=False, indent=2)
    path.write_text(out, encoding="utf-8", newline="\n")
    return True


def main() -> int:
    changed = 0
    for path in sorted(BLOG_EN_DIR.glob("*.json")):
        if strip_file(path):
            print(f"  [stripped] {path.name}")
            changed += 1
        else:
            print(f"  [clean]    {path.name}")
    print(f"Done: {changed} file(s) updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
