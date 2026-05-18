# n8n Workflows — AliGlobalShop

Tutti i workflow dispatchano un GitHub Actions workflow nel repo `Gallo93/aliglobalshop`.

| # | File | Trigger | GitHub Action dispatched | Note |
|---|------|---------|--------------------------|------|
| 01 | `01_fetch_products_daily.json` | cron `0 1 * * *` (02:00 Europe/Rome) | `fetch_products.yml` | Aggiorna `_data/products/en/*.json` |
| 02 | `02_update_prices_6h.json` | cron `0 */6 * * *` | `update_prices.yml` | Aggiorna prezzi + Resend alert |
| 03 | `03_build_site_webhook.json` | webhook POST `/webhook/build-site` | `deploy.yml` | Rebuild site on demand |
| 04 | `04_flash_sale_hourly.json` | cron `0 * * * *` | `flash_sale.yml` | Aggiorna `_data/flash-sale/en.json` |
| 05 | `05_fetch_coupons_daily.json` | cron `0 5 * * *` (06:00 Europe/Rome) | `fetch_coupons.yml` | Aggiorna `_data/coupons/en.json` |

Tutti i workflow hanno `settings.timezone: "Europe/Rome"`.

## Prerequisiti

### 1. Env vars Railway (istanza n8n)

Settare sul service Railway `aliglobalshop-production`:

| Variabile | Valore | Note |
|-----------|--------|------|
| `GITHUB_TOKEN` | PAT GitHub | Scope: `repo`, `workflow`. Letto da ogni nodo HTTP Request come `Bearer {{$env.GITHUB_TOKEN}}` per chiamare `actions/workflows/*/dispatches` |

Dopo aver settato la variabile, riavviare il service Railway una volta perché n8n carichi `process.env.GITHUB_TOKEN` nei worker.

### 2. API key n8n

Se l'attuale ritorna 401, rigenerare da `https://aliglobalshop-production.up.railway.app/settings/api`:

1. Login UI (basic auth admin)
2. Settings → n8n API → "Create an API key"
3. Salvare in `project_aliglobalshop_infra.md` (memoria) e in `.env` locale come `N8N_API_KEY`

## Import & activate (post-credenziali)

Una volta che `N8N_API_KEY` è valida e `GITHUB_TOKEN` è su Railway, runnare `import.sh` (vedi sotto) oppure le snippet curl manuali.

### Quick start (one-liner)

```bash
export N8N_BASE_URL="https://aliglobalshop-production.up.railway.app"
export N8N_API_KEY="<la-key-rigenerata>"
bash _infra/n8n/workflows/import.sh
```

Lo script:
1. POST `/api/v1/workflows` per ognuno dei 5 JSON
2. Estrae l'`id` dalla response
3. POST `/api/v1/workflows/{id}/activate` per attivare
4. Stampa una tabella finale `file -> id -> active`

### Snippet curl manuali (debug)

**Import singolo workflow:**
```bash
curl -sS -X POST "$N8N_BASE_URL/api/v1/workflows" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  --data @_infra/n8n/workflows/01_fetch_products_daily.json
# response: { "id": "abc123", "name": "01 Fetch Products Daily", ... }
```

**Attivazione singola:**
```bash
curl -sS -X POST "$N8N_BASE_URL/api/v1/workflows/<id>/activate" \
  -H "X-N8N-API-KEY: $N8N_API_KEY"
```

**Lista workflow attivi (verifica):**
```bash
curl -sS "$N8N_BASE_URL/api/v1/workflows?active=true" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" | jq '.data[] | {id, name, active}'
```

**Trigger manuale del Build Site webhook (test):**
```bash
curl -sS -X POST "$N8N_BASE_URL/webhook/build-site" \
  -H "Content-Type: application/json" -d '{}'
# atteso: { "message": "Workflow was started" } e dispatch su Gallo93/aliglobalshop deploy.yml
```

## Troubleshooting

| Errore | Causa probabile | Fix |
|--------|-----------------|-----|
| `401 unauthorized` su `/api/v1/*` | API key revocata o n8n riavviato con `N8N_ENCRYPTION_KEY` diverso | Rigenera da UI Settings→API |
| `404 Not Found` su `actions/workflows/*/dispatches` | Nome file workflow GHA errato | Verifica `.github/workflows/` esista quel file |
| `403 Resource not accessible by integration` sul dispatch GitHub | PAT senza scope `workflow` | Rigenera PAT con scope `repo` + `workflow` |
| Nodo HTTP n8n: `Could not get parameter "GITHUB_TOKEN"` | Env var non settata su Railway o n8n non riavviato | Aggiungi var, redeploy service |
| Webhook 03 risponde ma deploy non parte | `ref` errato o branch protetto | Body deve essere `{"ref": "main"}` e `main` deve esistere |
