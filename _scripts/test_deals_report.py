"""Test deterministico (no rete, nessuna POST) della pagina-report di dati.

La pagina /{lang}/aliexpress-deals-report-2026/ e' un asset linkabile: ogni
numero deve derivare da un campo REALE in _data/ (prezzo, original_price,
discount_pct, category, rating, reviews_count). Questo test e' la garanzia
anti-fabbricazione: ricalcola gli aggregati in modo indipendente e verifica che
combacino con compute_deals_report, poi controlla il render, la presenza in
tutte le 5 lingue, l'indicizzabilita', il JSON-LD Dataset, l'assenza di em-dash
e che i prezzi passino da format_price.

Eseguibile a mano (`python _scripts/test_deals_report.py`) o via pytest.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import build  # noqa: E402

SITE = "https://aliglobalshop.net"
TEMPLATE = Path(__file__).parent.parent / "_templates" / "report.html"
CONFIG = json.loads((Path(__file__).parent.parent / "_data" / "config.json").read_text(encoding="utf-8"))


def _num(x):
    try:
        return float(str(x).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _independent_stats(products_by_cat, flash, coupons):
    """Ricalcolo indipendente delle metriche chiave, formule scritte a mano
    (non riusa build.compute_deals_report) per fare da contro-prova."""
    prods = []
    for slug in sorted(products_by_cat):
        for p in products_by_cat[slug].get("products", []):
            prods.append(p)
    disc = [p["discount_pct"] for p in prods if isinstance(p.get("discount_pct"), (int, float))]
    prices = [v for v in (_num(p.get("price")) for p in prods) if v is not None]
    ratings = [p["rating"] for p in prods if isinstance(p.get("rating"), (int, float)) and p["rating"] > 0]
    per_niche = {}
    for slug in sorted(products_by_cat):
        items = products_by_cat[slug].get("products", [])
        d = [p["discount_pct"] for p in items if isinstance(p.get("discount_pct"), (int, float))]
        per_niche[slug] = {
            "count": len(items),
            "avg_discount_pct": round(sum(d) / len(d), 1) if d else 0.0,
        }
    return {
        "products_tracked": len(prods),
        "avg_discount_pct": round(sum(disc) / len(disc), 1) if disc else 0.0,
        "total_reviews": sum(p.get("reviews_count") or 0 for p in prods),
        "rated_count": len(ratings),
        "min_price": round(min(prices), 2) if prices else None,
        "max_price": round(max(prices), 2) if prices else None,
        "deals_tracked": len(flash),
        "coupons_tracked": len(coupons),
        "per_niche": per_niche,
    }


def main() -> int:
    failures = []
    products = build.load_products("en")
    flash, _ = build.load_flash_deals("en")
    coupons, _ = build.load_coupons("en")

    stats = build.compute_deals_report(products, flash, coupons, today="2026-06-26")
    if stats is None:
        print("FALLITO: dati insufficienti, compute_deals_report ha restituito None")
        return 1

    # (a) anti-fabbricazione: confronto col ricalcolo indipendente.
    ref = _independent_stats(products, flash, coupons)
    checks = {
        "products_tracked": stats["products_tracked"] == ref["products_tracked"],
        "avg_discount_pct": stats["avg_discount_pct"] == ref["avg_discount_pct"],
        "total_reviews": stats["total_reviews"] == ref["total_reviews"],
        "rated_count": stats["rated_count"] == ref["rated_count"],
        "min_price": stats["min_price"] == ref["min_price"],
        "max_price": stats["max_price"] == ref["max_price"],
        "deals_tracked": stats["deals_tracked"] == ref["deals_tracked"],
        "coupons_tracked": stats["coupons_tracked"] == ref["coupons_tracked"],
    }
    for k, ok in checks.items():
        if not ok:
            failures.append(f"[a] {k}: report={stats.get(k)!r} vs ricalcolo={ref.get(k)!r}")
        else:
            print(f"[a] OK {k} = {stats.get(k)!r}")
    # niche per niche
    for n in stats["niches"]:
        rn = ref["per_niche"][n["slug"]]
        if n["count"] != rn["count"] or n["avg_discount_pct"] != rn["avg_discount_pct"]:
            failures.append(f"[a] niche {n['slug']}: {n} vs {rn}")
        else:
            print(f"[a] OK niche {n['slug']} count={n['count']} disc={n['avg_discount_pct']}")
    # le price band sommano al numero di prodotti con prezzo valido
    band_total = sum(b["count"] for b in stats["price_bands"])
    n_priced = len([1 for slug in products for p in products[slug]["products"] if _num(p.get("price")) is not None])
    if band_total != n_priced:
        failures.append(f"[a] price_bands somma {band_total} != prodotti con prezzo {n_priced}")
    else:
        print(f"[a] OK price_bands somma {band_total}")

    # (b) determinismo: due chiamate identiche -> output identico.
    again = build.compute_deals_report(products, flash, coupons, today="2026-06-26")
    if again != stats:
        failures.append("[b] compute_deals_report NON deterministico")
    else:
        print("[b] OK compute_deals_report deterministico")

    # (c) render EN: i numeri renderizzati DEVONO comparire (anti-fabbricazione lato vista).
    T_en = build.load_i18n("en")
    body = build.render_report_body(stats, T_en, SITE, "en")
    must_appear = [
        str(stats["products_tracked"]),
        str(stats["total_reviews"]),
        f'{stats["avg_discount_pct"]:.1f}%',
    ]
    for n in stats["niches"]:
        must_appear.append(str(n["count"]))
    for token in must_appear:
        if token not in body:
            failures.append(f"[c] token {token!r} assente dal body renderizzato")
    if must_appear and not failures:
        print(f"[c] OK {len(must_appear)} numeri reali presenti nel render")

    # (c) niente em-dash, niente noindex, prezzi via format_price (simbolo $ in EN),
    #     grafici CSS e link al dataset presenti.
    if "—" in body or "&mdash;" in body or "&#8212;" in body:
        failures.append("[c] em-dash presente nel body")
    if "noindex" in body.lower():
        failures.append("[c] body contiene noindex")
    if "$" not in body:
        failures.append("[c] nessun prezzo formattato ($) nel render EN")
    if "report-bar__fill" not in body:
        failures.append("[c] grafico a barre CSS assente")
    if f"{build.REPORT_SLUG}.json" not in body:
        failures.append("[c] link al dataset assente dal blocco cite")
    if not failures:
        print("[c] OK render: no em-dash, no noindex, prezzi $, barre CSS, link dataset")

    # (d) prezzi localizzati: con una valuta EUR il render usa format_price EUR.
    T_eur = json.loads(json.dumps(T_en))
    T_eur.setdefault("_meta", {})["currency"] = "EUR"
    T_eur["_meta"]["currency_symbol"] = "&euro;"
    body_eur = build.render_report_body(stats, T_eur, SITE, "it")
    if "&euro;" not in body_eur:
        failures.append("[d] render EUR non usa format_price (nessun &euro;)")
    elif "—" in body_eur:
        failures.append("[d] em-dash nel render EUR")
    else:
        print("[d] OK render EUR usa format_price")

    # (e) presenza in tutte le 5 lingue configurate + sitemap + hreflang.
    langs = CONFIG.get("languages", [])
    if set(langs) != {"en", "it", "es", "de", "fr"}:
        failures.append(f"[e] lingue inattese in config: {langs}")
    for lang in langs:
        T = build.load_i18n(lang)
        b = build.render_report_body(stats, T, SITE, lang)
        if not b.strip():
            failures.append(f"[e] render vuoto per {lang}")
        if "—" in b:
            failures.append(f"[e] em-dash nel render {lang}")
    # la sitemap include lo slug report per ogni lingua
    for lang in langs:
        url = f"{SITE}/{lang}/{build.REPORT_SLUG}/"
        hl = build.hreflang_alternates(SITE, f"{build.REPORT_SLUG}/", langs, "en")
        if f'hreflang="{lang}"' not in hl or url not in hl:
            failures.append(f"[e] hreflang/url report mancante per {lang}")
    if not failures:
        print(f"[e] OK report presente e linkato in {len(langs)} lingue")

    # (f) slug indicizzabile: ASCII, lowercase-hyphen, <= 60.
    slug = build.REPORT_SLUG
    if not slug.isascii() or slug.lower() != slug or len(slug) > 60 or " " in slug:
        failures.append(f"[f] REPORT_SLUG non valido: {slug!r}")
    else:
        print(f"[f] OK slug {slug!r}")

    # (f) template indicizzabile (no noindex) con canonical, hreflang e Dataset JSON-LD.
    tpl = TEMPLATE.read_text(encoding="utf-8")
    for needle in ("{{canonical_url}}", "{{hreflang_alternates}}", "{{dataset_jsonld}}", "{{report_body_html}}"):
        if needle not in tpl:
            failures.append(f"[f] placeholder {needle} assente dal template")
    if "noindex" in tpl.lower():
        failures.append("[f] template report.html contiene noindex")
    if "{{canonical_url}}" in tpl and "noindex" not in tpl.lower():
        print("[f] OK template indicizzabile con canonical/hreflang/dataset")

    # (g) JSON-LD Dataset valido + dataset pubblico coerente con le metriche.
    jsonld = build.report_dataset_jsonld(stats, SITE)
    try:
        j = json.loads(jsonld)
        assert j["@type"] == "Dataset"
        assert j["distribution"][0]["contentUrl"].endswith(f"{build.REPORT_SLUG}.json")
        print("[g] OK JSON-LD Dataset valido")
    except Exception as exc:
        failures.append(f"[g] JSON-LD Dataset non valido: {exc}")
    ds = build.report_dataset_obj(stats, SITE)
    if ds["metrics"]["products_tracked"] != stats["products_tracked"]:
        failures.append("[g] dataset products_tracked != stats")
    if ds.get("currency") != "USD":
        failures.append("[g] dataset non dichiara currency USD")
    if not failures:
        print("[g] OK dataset pubblico coerente (USD)")

    print()
    if failures:
        print(f"FALLITI {len(failures)} controlli:")
        for f in failures:
            print("  -", f)
        return 1
    print("TUTTI I CONTROLLI PASSATI")
    return 0


def test_deals_report():
    """Entry-point pytest."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
