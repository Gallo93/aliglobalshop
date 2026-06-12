"""
Replace em-dashes in the EN blog sources so they never reach the rendered site.

The site style bans the em-dash (U+2014) in visible text, but Claude/argos
translations preserve whatever is in the EN source, so a single em-dash in an
EN article propagates to EN/IT/ES/DE/FR. This one-shot, idempotent cleaner
rewrites em-dashes in the EN sources at the root; build.py keeps a render-time
safety net (sanitize_em_dash) as a second line of defence for current output
and any future article.

An em-dash is replaced with a comma + space (", "), the most common sensible
reading, then any resulting doubled space / space-before-comma is collapsed.
Fields cleaned: content_html, title, meta_desc / meta_description. Running it
again on an already-clean file is a no-op.

Usage:
    python _scripts/strip_em_dash.py
"""
import json
import re
from pathlib import Path

BLOG_EN_DIR = Path(__file__).resolve().parent.parent / "_data" / "blog" / "en"

# U+2014 em-dash plus its common HTML entity spellings.
_EM_DASH_RE = re.compile(r"—|&#8212;|&#x2014;|&mdash;")
_FIELDS = ("content_html", "title", "meta_desc", "meta_description")


def clean_text(text: str) -> str:
    out = _EM_DASH_RE.sub(", ", text)
    # Collapse artefacts from the substitution: " , " -> ", ", ",  " -> ", ".
    out = re.sub(r"\s+,", ",", out)
    out = re.sub(r",\s{2,}", ", ", out)
    return out


def clean_file(path: Path) -> bool:
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    for field in _FIELDS:
        val = data.get(field)
        if isinstance(val, str) and _EM_DASH_RE.search(val):
            data[field] = clean_text(val)
            changed = True
    if not changed:
        return False
    # Match the existing on-disk format: 2-space indent, UTF-8, LF, no final NL.
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8", newline="\n")
    return True


def main() -> int:
    changed = 0
    for path in sorted(BLOG_EN_DIR.glob("*.json")):
        if clean_file(path):
            print(f"  [cleaned] {path.name}")
            changed += 1
        else:
            print(f"  [clean]   {path.name}")
    print(f"Done: {changed} file(s) updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
