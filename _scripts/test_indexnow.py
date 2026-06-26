"""Test deterministico (no rete, nessuna POST reale) del ping IndexNow.

IndexNow su AliGlobalShop e' wired nel flusso CI: la key pubblica vive in
_data/config.json (indexnow_key), build.py la scrive come <key>.txt nella root
pubblicata, e dopo il deploy GitHub Pages il job `indexnow` chiama
indexnow_ping.py per submittare gli URL della sitemap.

Questo smoke test verifica, senza toccare la rete:
  a) extract_urls() legge i <loc> di una sitemap (con e senza namespace) e
     ritorna [] in modo pulito se il file manca;
  b) submit() costruisce il payload IndexNow corretto (host, key, keyLocation,
     urlList) verso l'endpoint giusto, con method POST e content-type JSON,
     intercettando urlopen via monkeypatch (nessuna richiesta vera parte);
  c) main() salta in modo pulito quando la key non e' configurata;
  d) la key reale in _data/config.json e' una stringa esadecimale di 32 char
     (formato richiesto da IndexNow) e l'endpoint resta quello ufficiale.

Eseguibile a mano (`python _scripts/test_indexnow.py`) o via pytest.
Esce con codice != 0 al primo fallimento.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import indexnow_ping  # noqa: E402

CONFIG_PATH = Path(__file__).parent.parent / "_data" / "config.json"

SITEMAP_WITH_NS = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    "  <url><loc>https://aliglobalshop.net/en/</loc></url>\n"
    "  <url><loc>https://aliglobalshop.net/it/</loc></url>\n"
    "  <url><loc>https://aliglobalshop.net/en/blog/</loc></url>\n"
    "</urlset>\n"
)
SITEMAP_NO_NS = (
    "<urlset>\n"
    "  <url><loc>https://aliglobalshop.net/es/</loc></url>\n"
    "</urlset>\n"
)


class _FakeResponse:
    """Context manager che imita la risposta di urlopen senza rete."""

    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def main() -> int:
    failures = []
    tmp_dir = Path(__file__).parent

    # (a) extract_urls con namespace standard
    p_ns = tmp_dir / "_tmp_sitemap_ns.xml"
    p_ns.write_text(SITEMAP_WITH_NS, encoding="utf-8")
    urls = indexnow_ping.extract_urls(p_ns)
    p_ns.unlink()
    expected = [
        "https://aliglobalshop.net/en/",
        "https://aliglobalshop.net/it/",
        "https://aliglobalshop.net/en/blog/",
    ]
    if urls != expected:
        failures.append(f"[a] extract_urls (ns) -> {urls}, atteso {expected}")
    else:
        print(f"[a] OK extract_urls namespace: {len(urls)} URL")

    # (a) extract_urls fallback senza namespace
    p_no = tmp_dir / "_tmp_sitemap_nons.xml"
    p_no.write_text(SITEMAP_NO_NS, encoding="utf-8")
    urls_no = indexnow_ping.extract_urls(p_no)
    p_no.unlink()
    if urls_no != ["https://aliglobalshop.net/es/"]:
        failures.append(f"[a] extract_urls (no-ns) -> {urls_no}")
    else:
        print("[a] OK extract_urls senza namespace")

    # (a) file mancante -> lista vuota, nessuna eccezione
    missing = indexnow_ping.extract_urls(tmp_dir / "_does_not_exist.xml")
    if missing != []:
        failures.append(f"[a] sitemap mancante -> {missing}, atteso []")
    else:
        print("[a] OK sitemap mancante -> []")

    # (b) submit costruisce il payload corretto, intercettando urlopen
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["headers"] = {k.lower(): v for k, v in req.header_items()}
        captured["body"] = json.loads(req.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _FakeResponse()

    orig_urlopen = indexnow_ping.urllib.request.urlopen
    indexnow_ping.urllib.request.urlopen = fake_urlopen
    try:
        indexnow_ping.submit(
            "aliglobalshop.net",
            "1d02319ae115404a92a1930cfa683e8a",
            ["https://aliglobalshop.net/en/", "https://aliglobalshop.net/it/"],
        )
    finally:
        indexnow_ping.urllib.request.urlopen = orig_urlopen

    body = captured.get("body", {})
    checks = {
        "endpoint": captured.get("url") == indexnow_ping.ENDPOINT,
        "method POST": captured.get("method") == "POST",
        "content-type json": "json" in captured.get("headers", {}).get("content-type", ""),
        "host": body.get("host") == "aliglobalshop.net",
        "key": body.get("key") == "1d02319ae115404a92a1930cfa683e8a",
        "keyLocation": body.get("keyLocation")
        == "https://aliglobalshop.net/1d02319ae115404a92a1930cfa683e8a.txt",
        "urlList": body.get("urlList")
        == ["https://aliglobalshop.net/en/", "https://aliglobalshop.net/it/"],
    }
    for label, ok in checks.items():
        if not ok:
            failures.append(f"[b] payload {label} errato: {captured!r}")
        else:
            print(f"[b] OK payload {label}")

    # (c) main() salta pulito senza key (load_config mockata vuota)
    orig_load = indexnow_ping.load_config
    indexnow_ping.load_config = lambda: {}
    called = {"submit": False}

    def fail_submit(*args, **kwargs):
        called["submit"] = True

    orig_submit = indexnow_ping.submit
    indexnow_ping.submit = fail_submit
    try:
        indexnow_ping.main()
    finally:
        indexnow_ping.load_config = orig_load
        indexnow_ping.submit = orig_submit
    if called["submit"]:
        failures.append("[c] main() ha chiamato submit senza key configurata")
    else:
        print("[c] OK main() salta senza key")

    # (d) key reale: 32 char esadecimali, endpoint ufficiale
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        key = cfg.get("indexnow_key", "")
        if len(key) != 32 or any(c not in "0123456789abcdef" for c in key):
            failures.append(f"[d] indexnow_key non e' 32 hex minuscoli: {key!r}")
        else:
            print(f"[d] OK indexnow_key valida ({key})")
    except Exception as exc:
        failures.append(f"[d] config.json illeggibile: {exc}")
    if indexnow_ping.ENDPOINT != "https://api.indexnow.org/indexnow":
        failures.append(f"[d] endpoint inatteso: {indexnow_ping.ENDPOINT}")

    print()
    if failures:
        print(f"FALLITI {len(failures)} controlli:")
        for fail in failures:
            print("  -", fail)
        return 1
    print("TUTTI I CONTROLLI PASSATI")
    return 0


def test_indexnow():
    """Entry-point pytest."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
