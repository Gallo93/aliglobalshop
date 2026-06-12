# AliGlobalShop.net

Sito affiliazione AliExpress — HTML statico, SEO internazionale, automazione n8n + AI.
Commissioni affiliate 3–9% per vendita generata. Zero magazzino, zero spedizioni.
**LIVE su https://aliglobalshop.net** (dominio dal 2026-05-22) in 5 lingue: EN, IT, ES, DE, FR.

## Stack
- **Frontend:** HTML statico generato da `_scripts/build.py` — 5 lingue (en/it/es/de/fr)
- **Hosting:** GitHub Pages su `aliglobalshop.net` (deploy via GitHub Actions su ogni push)
- **Automation:** n8n self-hosted su Railway — 6 workflow attivi (fetch, prezzi, build, flash-sale, coupon, price-alert webhook)
- **Images:** Cloudinary (free tier) — tutte le immagini re-hosted in WebP, CDN globale
- **Products:** AliExpress Affiliate API (`portals.aliexpress.com`)
- **AI Content:** Anthropic API `claude-sonnet-4-6` — blog EN 1 articolo/die (ridotto da 2 il 2026-06-12)
- **Traduzioni:** PRODOTTI via argostranslate (CI, gratis, offline); **BLOG via Claude** sonnet-4-6 (dal 2026-06-12, qualità nativa — toggle `BLOG_TRANSLATOR=claude|argos`, default claude) — IT/ES/DE/FR da EN
- **Email:** Resend (free tier) — price drop alerts (NON ancora configurato; i lead si accumulano nel workflow n8n "06 Price Alert")

## Ordine costruzione — NON deviare
```
FASE 0  → Obsidian vault (fatto)
FASE 1  → GitHub + Railway + n8n + verifica API (fatto)
FASE 2  → Fetch prodotti EN → JSON → immagini su Cloudinary (fatto)
FASE 3  → 5 workflow n8n (fatto)
FASE 4  → Template HTML EN + build.py + blog AI (fatto)
FASE 5  → Dominio + live EN (fatto — aliglobalshop.net)
FASE 6  → Espansione lingue: IT → ES → DE → FR (TUTTE FATTE)
```

## Struttura cartelle
```
_data/products/en/           → JSON prodotti per categoria
_data/products/{it,es,de,fr}/ → prodotti tradotti (title localizzato, prezzi EUR)
_data/products/_article/     → prodotti matchati agli articoli blog
_data/blog/{en,it,es,de,fr}/ → articoli blog (yyyy-mm-dd-slug.json, slug SEMPRE EN)
_data/flash-sale/en.json     → SuperDeals con timestamp scadenza
_data/coupons/en.json        → coupon codes aggiornati daily
_data/i18n/                  → dizionari stringhe UI per lingua (en/it/es/de/fr.json)
_data/.translate_cache.json  → cache hash traduzioni (file di stato, committato)
_data/config.json            → lingue attive, nicchie, site_url, currencies, fx_rates
_templates/                  → template HTML (product, category, blog-post, home…)
_templates/{it,es,de,fr}/    → static pages per lingua (about, contact, privacy)
_scripts/                    → build.py, fetch_products.py, generate_blog.py,
                               update_prices.py, translate_content.py, ci_install_argos.py,
                               strip_em_dash.py, strip_legacy_disclaimer.py
en/ it/ es/ de/ fr/          → siti generati IN CI — MAI committare HTML buildato
assets/css/ js/ img/
```

## Nicchie (tutte le lingue)
`electronics` · `smart-home` · `sport` · `gadgets`

## Env vars (in .env — mai committare)
```
ALIEXPRESS_APP_KEY, ALIEXPRESS_APP_SECRET, ALIEXPRESS_TRACKING_ID
ANTHROPIC_API_KEY
CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
RESEND_API_KEY
SITE_URL=https://aliglobalshop.net
```

## Convenzioni
- Python: snake_case, try/except su ogni chiamata API esterna
- HTML: semantic, BEM, lazy loading su tutte le img, width+height sempre espliciti
- JS: vanilla puro, nessun framework, nessuna dipendenza esterna
- Slug: lowercase, trattini, max 60 chars, solo ASCII — SEMPRE EN, anche su IT/ES/DE/FR
- JSON date: ISO8601 — valori mancanti: `null`
- Niente em-dash (—) nei testi visibili del sito — `build.py` ha una safety net (`sanitize_em_dash`) che li elimina al build su tutte le lingue (em-dash letterale + entità)
- Prezzi: SOLO via `format_price(value, lang)` di build.py (USD `$11.56` su EN, EUR `11,56 €` su IT/ES/DE/FR)
- Link affiliate: `rel="nofollow sponsored noopener"` + target _blank; negli articoli le card prodotto linkano DIRETTO all'affiliate_url (mai URL interni costruiti dallo slug articolo)
- Articolo blog con campo `redirect_to` = stub redirect (meta refresh 0 + canonical + noindex, fuori da sitemap/blog index) — il JSON resta nel repo
- reading_time articoli calcolato dal conteggio parole reale (`reading_time_min()` in build.py, ~200 wpm); `<title>` blog troncato a 43 senza frammenti orfani (`truncate_word_boundary`)
- Privacy: NIENTE dati personali del titolare (rimandato ~settembre 2026); i flag `<!-- rilettura umana -->` nei template restano
- Mai heredoc Python multilinea dentro `run: |` nei workflow GitHub (YAML invalido silenzioso): usare script in `_scripts/` chiamati a una riga

## Convenzioni i18n
- **Regola d'oro:** quando si tocca una lingua, le altre restano byte-identiche nell'OUTPUT BUILDATO (verifica con build + diff/hash, non sui sorgenti).
- **Traduzioni:** `_scripts/translate_content.py --lang X` traduce prodotti e blog, converte i prezzi in EUR via `fx_rates` (config.json, override env `FX_RATE_<CUR>`) e ripunta i link interni `/en/`→`/<lang>/`. `primary_keyword` resta EN.
  - **PRODOTTI:** argostranslate (offline, gratis) + glossario override per i termini tech + normalizzazione `$`→`€` nei titoli.
  - **BLOG (dal 2026-06-12):** **Claude** sonnet-4-6 (`BLOG_TRANSLATOR=claude|argos`, default claude; `ANTHROPIC_MODEL` override). Qualità nativa: traduce title e tutti gli heading, termini tech corretti; preserva HTML + token prezzo `$` verbatim (il build li converte in €) + slug/primary_keyword EN; link interni riscritti deterministicamente. Su errore API/parse: log + mantiene il sorgente EN (no crash). I prezzi `$` nel `content_html` EN restano e il build li localizza in € via `localize_prices_in_html`.
  - Cache hash in `_data/.translate_cache.json`: cache_key via `.as_posix()`, ritraduce solo se il sorgente EN cambia (`--force` per backfill). I fix manuali ai titoli sopravvivono finché il sorgente EN resta invariato.
- **Aggiungere una lingua:** oltre ai punti sopra, PERSISTERE le voci cache della nuova lingua in `.translate_cache.json` (hash == sorgente EN) nello stesso commit dei titoli curati, altrimenti il primo run CI li sovrascrive. Se la CI è avanzata su main tra apertura PR e merge, ri-mergiare main nel branch (conflitto cache risolto in union) e ritradurre i prodotti dai sorgenti EN aggiornati.

## Fasi completate
- [x] FASE 0 — Vault Obsidian
- [x] FASE 1 — Infrastruttura
- [x] FASE 2 — Primo fetch EN
- [x] FASE 3 — Workflow n8n
- [x] FASE 4 — Template + Blog AI
- [x] FASE 5 — Dominio + Live EN (aliglobalshop.net)
- [x] FASE 6 — IT+ES+DE live (2026-06-04) · FR live (2026-06-07, PR #7 merge 3a2cf94) — COMPLETATA
- [x] AUDIT TOTALE 2026-06 — 15 fix F1-F14 (PR #6, merge f6429292), test live 12/12 PASS
- [x] BLOG via Claude + Navbar one-line (2026-06-12) — traduzione blog argos→Claude (PR #10/#13), backfill 84 articoli, navbar una riga tutte le lingue (PR #11/#12)

## Dettagli completi
Vedi `docs/piano-progetto.md` per schema JSON prodotto, endpoint API, workflow n8n,
feature competitor, SEO rules, prompt blog template.
Il vault Obsidian (cartella locale "secondo cervello") è la fonte primaria di stato e decisioni.
