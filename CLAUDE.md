# AliGlobalShop.net

Sito affiliazione AliExpress — HTML statico, SEO internazionale, automazione n8n + AI.
Commissioni affiliate 3–9% per vendita generata. Zero magazzino, zero spedizioni.
**LIVE su https://aliglobalshop.net** (dominio dal 2026-05-22) in 4 lingue: EN, IT, ES, DE.

## Stack
- **Frontend:** HTML statico generato da `_scripts/build.py` — 4 lingue (en/it/es/de)
- **Hosting:** GitHub Pages su `aliglobalshop.net` (deploy via GitHub Actions su ogni push)
- **Automation:** n8n self-hosted su Railway — 6 workflow attivi (fetch, prezzi, build, flash-sale, coupon, price-alert webhook)
- **Images:** Cloudinary (free tier) — tutte le immagini re-hosted in WebP, CDN globale
- **Products:** AliExpress Affiliate API (`portals.aliexpress.com`)
- **AI Content:** Anthropic API `claude-sonnet-4-6` — blog EN 2 articoli/die
- **Traduzioni:** argostranslate in CI (gratis, offline) — IT/ES/DE da EN, con glossario override
- **Email:** Resend (free tier) — price drop alerts (NON ancora configurato; i lead si accumulano nel workflow n8n "06 Price Alert")

## Ordine costruzione — NON deviare
```
FASE 0  → Obsidian vault (fatto)
FASE 1  → GitHub + Railway + n8n + verifica API (fatto)
FASE 2  → Fetch prodotti EN → JSON → immagini su Cloudinary (fatto)
FASE 3  → 5 workflow n8n (fatto)
FASE 4  → Template HTML EN + build.py + blog AI (fatto)
FASE 5  → Dominio + live EN (fatto — aliglobalshop.net)
FASE 6  → Espansione lingue: IT → ES → DE (fatte) → FR (da fare, una alla volta)
```

## Struttura cartelle
```
_data/products/en/        → JSON prodotti per categoria
_data/products/{it,es,de}/ → prodotti tradotti (title localizzato, prezzi EUR)
_data/products/_article/  → prodotti matchati agli articoli blog
_data/blog/{en,it,es,de}/ → articoli blog (yyyy-mm-dd-slug.json, slug SEMPRE EN)
_data/flash-sale/en.json  → SuperDeals con timestamp scadenza
_data/coupons/en.json     → coupon codes aggiornati daily
_data/i18n/               → dizionari stringhe UI per lingua (en/it/es/de.json)
_data/config.json         → lingue attive, nicchie, site_url, currencies, fx_rates
_templates/               → template HTML (product, category, blog-post, home…)
_templates/{it,es,de}/    → static pages per lingua (about, contact, privacy)
_scripts/                 → build.py, fetch_products.py, generate_blog.py,
                            update_prices.py, translate_content.py, ci_install_argos.py
en/ it/ es/ de/           → siti generati IN CI — MAI committare HTML buildato
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
- Slug: lowercase, trattini, max 60 chars, solo ASCII — SEMPRE EN, anche su IT/ES/DE
- JSON date: ISO8601 — valori mancanti: `null`
- Niente em-dash (—) nei testi visibili del sito
- Prezzi: SOLO via `format_price(value, lang)` di build.py (USD `$11.56` su EN, EUR `11,56 €` su IT/ES/DE)
- Link affiliate: `rel="nofollow sponsored noopener"` + target _blank; negli articoli le card prodotto linkano DIRETTO all'affiliate_url (mai URL interni costruiti dallo slug articolo)
- Articolo blog con campo `redirect_to` = stub redirect (meta refresh 0 + canonical + noindex, fuori da sitemap/blog index) — il JSON resta nel repo
- Privacy: NIENTE dati personali del titolare (rimandato ~settembre 2026); i flag `<!-- rilettura umana -->` nei template restano
- Mai heredoc Python multilinea dentro `run: |` nei workflow GitHub (YAML invalido silenzioso): usare script in `_scripts/` chiamati a una riga

## Convenzioni i18n
- **Regola d'oro:** quando si tocca una lingua, le altre restano byte-identiche nell'OUTPUT BUILDATO (verifica con build + diff/hash, non sui sorgenti).
- **Traduzioni:** `_scripts/translate_content.py` (argostranslate EN→IT/ES/DE, parametrico `--lang`) traduce prodotti e blog, converte i prezzi in EUR via `fx_rates` (config.json, override env `FX_RATE_<CUR>`) e ripunta i link interni `/en/`→`/<lang>/`. Glossario override per i termini tech che argos sbaglia + normalizzazione `$`→`€` nei titoli. `primary_keyword` resta EN. Cache hash in `_data/.translate_cache.json`: ritraduce solo se il sorgente EN cambia, quindi i fix manuali ai titoli tradotti sopravvivono finché il sorgente EN resta invariato.

## Fasi completate
- [x] FASE 0 — Vault Obsidian
- [x] FASE 1 — Infrastruttura
- [x] FASE 2 — Primo fetch EN
- [x] FASE 3 — Workflow n8n
- [x] FASE 4 — Template + Blog AI
- [x] FASE 5 — Dominio + Live EN (aliglobalshop.net)
- [ ] FASE 6 — IT+ES+DE live (2026-06-04) · resta FR
- [x] AUDIT TOTALE 2026-06 — 15 fix F1-F14 (PR #6, merge f6429292), test live 12/12 PASS

## Dettagli completi
Vedi `docs/piano-progetto.md` per schema JSON prodotto, endpoint API, workflow n8n,
feature competitor, SEO rules, prompt blog template.
Il vault Obsidian (cartella locale "secondo cervello") è la fonte primaria di stato e decisioni.
