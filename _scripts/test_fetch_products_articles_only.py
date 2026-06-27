"""Test deterministico (no API, no rete, no secrets) del flag --articles-only di
fetch_products.main().

Verifica il SOLO dispatch di main():
  - articles_only=True  -> NON scorre le nicchie (fetch_niche mai chiamato),
    chiama fetch_article_products una volta;
  - articles_only=False -> chiama fetch_niche per ogni nicchia + article una volta.

fetch_niche e fetch_article_products sono sostituiti con stub che contano le
chiamate; APP_KEY/APP_SECRET e OUTPUT_DIR sono monkeypatchati sul modulo cosi
non serve nessuna rete/secret e non si tocca il repo reale.

Eseguibile a mano (`python _scripts/test_fetch_products_articles_only.py`) o via
pytest. Esce con codice != 0 al primo fallimento.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fetch_products as fp  # noqa: E402


class _Patched:
    """Context manager: stub di fetch_niche/fetch_article_products + APP key
    fittizie + OUTPUT_DIR in tmp. Conta le chiamate in self.calls."""

    def __init__(self, app_key="k", app_secret="s"):
        self.app_key = app_key
        self.app_secret = app_secret
        self.calls = {"niche": 0, "article": 0}
        self._saved = {}
        self._tmp = None

    def __enter__(self):
        self._saved = {
            "fetch_niche": fp.fetch_niche,
            "fetch_article_products": fp.fetch_article_products,
            "OUTPUT_DIR": fp.OUTPUT_DIR,
            "APP_KEY": fp.APP_KEY,
            "APP_SECRET": fp.APP_SECRET,
        }
        self._tmp = Path(tempfile.mkdtemp(prefix="fp-test-"))
        fp.OUTPUT_DIR = self._tmp / "en"
        fp.APP_KEY = self.app_key
        fp.APP_SECRET = self.app_secret

        def _stub_niche(niche, keywords):
            self.calls["niche"] += 1
            return []

        def _stub_article(blog_dir, article_output_dir):
            self.calls["article"] += 1

        fp.fetch_niche = _stub_niche
        fp.fetch_article_products = _stub_article
        return self

    def __exit__(self, *exc):
        for name, value in self._saved.items():
            setattr(fp, name, value)
        return False


def test_articles_only_skips_niches():
    with _Patched() as p:
        fp.main(articles_only=True)
    assert p.calls["niche"] == 0, f"niche loop NON deve girare, visto {p.calls['niche']}"
    assert p.calls["article"] == 1, f"article fetch atteso 1, visto {p.calls['article']}"
    print("[ok] articles_only=True: niche saltate, article 1x")


def test_full_run_does_both():
    with _Patched() as p:
        fp.main(articles_only=False)
    expected_niches = len(fp.NICHES)
    assert p.calls["niche"] == expected_niches, \
        f"niche atteso {expected_niches}, visto {p.calls['niche']}"
    assert p.calls["article"] == 1, f"article fetch atteso 1, visto {p.calls['article']}"
    print(f"[ok] articles_only=False: niche {expected_niches}x + article 1x")


def test_default_is_full_run():
    """Senza argomenti main() = comportamento storico (entrambi)."""
    with _Patched() as p:
        fp.main()
    assert p.calls["niche"] == len(fp.NICHES), "default deve scorrere le nicchie"
    assert p.calls["article"] == 1, "default deve fare anche l'article fetch"
    print("[ok] default (nessun flag) = run completo")


def test_guard_missing_keys():
    """Senza APP_KEY/APP_SECRET -> SystemExit, nessun fetch."""
    raised = False
    with _Patched(app_key="", app_secret="") as p:
        try:
            fp.main(articles_only=True)
        except SystemExit:
            raised = True
    assert raised, "main deve uscire (SystemExit) senza le chiavi API"
    assert p.calls == {"niche": 0, "article": 0}, "nessun fetch senza chiavi"
    print("[ok] guard: SystemExit senza chiavi API")


_TESTS = [
    test_articles_only_skips_niches,
    test_full_run_does_both,
    test_default_is_full_run,
    test_guard_missing_keys,
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
