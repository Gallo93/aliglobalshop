# AliGlobalShop.com

Sito affiliazione AliExpress — HTML statico, SEO internazionale, automazione n8n + AI.
Commissioni affiliate 3–9% per vendita generata. Zero magazzino, zero spedizioni.

## Stack
- **Frontend:** HTML statico generato da `_scripts/build.py`
- **Hosting:** GitHub Pages (deploy via GitHub Actions su ogni push)
- **Automation:** n8n self-hosted su Railway
- **CDN/DNS:** Cloudflare (cache, SSL, R2 per immagini)
- **Images:** Cloudflare R2 — tutte le immagini re-hosted in WebP
- **Products:** AliExpress Affiliate API (`portals.aliexpress.com`)
- **AI Content:** Anthropic API `claude-sonnet-4-20250514` — blog + traduzioni
- **Email:** Resend (free tier) — price drop alerts

## Ordine costruzione — NON deviare
```
FASE 0  → Obsidian vault (fatto)
FASE 1  → GitHub + Railway + n8n + Cloudflare R2 + verifica API
FASE 2  → Fetch prodotti EN → JSON → immagini su R2
FASE 3  → 5 workflow n8n (fetch, prezzi, build, flash-sale, coupon)
FASE 4  → Template HTML EN + build.py + blog AI (2 articoli/die)
FASE 5  → Staging OK 3gg → ACQUISTO DOMINIO → live EN
FASE 6  → Espansione lingue: IT → ES → DE → FR (una alla volta)
```
**Dominio si acquista SOLO dopo EN stabile in staging per 3 giorni.**

## Struttura cartelle
```
_data/products/en/        → JSON prodotti per categoria
_data/blog/en/            → articoli blog (yyyy-mm-dd-slug.json)
_data/flash-sale/en.json  → SuperDeals con timestamp scadenza
_data/coupons/en.json     → coupon codes aggiornati daily
_data/config.json         → lingue attive, nicchie, site_url
_templates/               → template HTML (product, category, blog-post, home…)
_scripts/                 → build.py, fetch_products.py, generate_blog.py, update_prices.py
en/                       → sito EN generato (prima lingua)
assets/css/ js/ img/
```

## Nicchie EN (partenza)
`electronics` · `smart-home` · `sport` · `gadgets`

## Env vars (in .env — mai committare)
```
ALIEXPRESS_APP_KEY, ALIEXPRESS_APP_SECRET, ALIEXPRESS_TRACKING_ID
ANTHROPIC_API_KEY
CF_R2_ACCOUNT_ID, CF_R2_ACCESS_KEY_ID, CF_R2_SECRET_ACCESS_KEY
CF_R2_BUCKET_NAME=aliglobalshop-images
RESEND_API_KEY
SITE_URL=https://gallo93.github.io/aliglobalshop
```

## Convenzioni
- Python: snake_case, try/except su ogni chiamata API esterna
- HTML: semantic, BEM, lazy loading su tutte le img, width+height sempre espliciti
- JS: vanilla puro, nessun framework, nessuna dipendenza esterna
- Slug: lowercase, trattini, max 60 chars, solo ASCII
- JSON date: ISO8601 — valori mancanti: `null`

## Fasi completate
- [x] FASE 0 — Vault Obsidian
- [x] FASE 1 — Infrastruttura
- [ ] FASE 2 — Primo fetch EN
- [ ] FASE 3 — Workflow n8n
- [ ] FASE 4 — Template + Blog AI
- [ ] FASE 5 — Dominio + Live EN
- [ ] FASE 6 — IT / ES / DE / FR

## Dettagli completi
Vedi `docs/piano-progetto.md` per schema JSON prodotto, endpoint API, workflow n8n,
feature competitor, SEO rules, prompt blog template.

## URL infrastruttura
- GitHub Pages: https://gallo93.github.io/aliglobalshop
- GitHub repo: https://github.com/Gallo93/aliglobalshop
- n8n Railway: (da impostare dopo deploy)
