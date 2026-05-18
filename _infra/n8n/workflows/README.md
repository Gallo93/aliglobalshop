# n8n Workflows — AliGlobalShop

Tutti i workflow dispatchano un GitHub Actions workflow nel repo `Gallo93/aliglobalshop`.

## Stato live (importati 2026-05-18)

| # | Workflow ID | Nome | Trigger | GitHub Action | Active |
|---|-------------|------|---------|---------------|--------|
| 01 | `0VsRUr5adepDMInD` | 01 Fetch Products Daily | cron `0 1 * * *` (02:00 Europe/Rome) | `fetch_products.yml` | true |
| 02 | `ojL3gvnxh8DeubUK` | 02 Update Prices (6h) | cron `0 */6 * * *` | `update_prices.yml` | true |
| 03 | `ST3hpa5mjKc6CexB` | 03 Build Site (webhook) | webhook POST `/webhook/build-site` | `deploy.yml` | true |
| 04 | `i6mxfiEdl2iNMZDh` | 04 Flash Sale (hourly) | cron `0 * * * *` | `flash_sale.yml` | true |
| 05 | `Xh5H3kNWkDgvH24c` | 05 Fetch Coupons Daily | cron `0 5 * * *` (06:00 Europe/Rome) | `fetch_coupons.yml` | true |

Tutti con `settings.timezone: "Europe/Rome"`.

## Autenticazione GitHub API

I nodi HTTP Request usano una **credential n8n** di tipo `httpHeaderAuth` invece di `{{$env.GITHUB_TOKEN}}` (env var su Railway non disponibile via account token).

Credential salvata su n8n:
- **ID**: `USwcldHXwp1fbqKM`
- **Nome**: `GitHub Actions Dispatch`
- **Tipo**: `httpHeaderAuth`
- **Header**: `Authorization: Bearer <gho_xxx>` (GitHub Personal Access Token, owner `Gallo93`, scope `repo`)

Referenziata in ogni nodo HTTP come:
```json
"credentials": {
  "httpHeaderAuth": { "id": "USwcldHXwp1fbqKM", "name": "GitHub Actions Dispatch" }
}
```

## Re-import (in caso di reset n8n)

Se l'istanza n8n viene resettata e i workflow vanno persi, ricreare nell'ordine:

1. Creare la credential HTTP Header Auth:
```bash
curl -sS -X POST "$N8N_BASE_URL/api/v1/credentials" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "GitHub Actions Dispatch",
    "type": "httpHeaderAuth",
    "data": { "name": "Authorization", "value": "Bearer <gho_xxx>" }
  }'
# Estrarre l'id restituito
```

2. Aggiornare il campo `credentials.httpHeaderAuth.id` nei 5 JSON con il nuovo credential ID.

3. Lanciare `import.sh` per import + activate dei 5 workflow.

## Test rapido

**Lista workflow attivi:**
```bash
curl -sS "$N8N_BASE_URL/api/v1/workflows?active=true" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" | jq '.data[] | {id, name, active}'
```

**Trigger manuale Build Site (test deploy.yml dispatch):**
```bash
curl -sS -X POST "$N8N_BASE_URL/webhook/build-site" \
  -H "Content-Type: application/json" -d '{}'
# atteso: { "message": "Workflow was started" }
```

**Verificare run su GitHub Actions:**
```bash
curl -sS "https://api.github.com/repos/Gallo93/aliglobalshop/actions/runs?per_page=5" \
  -H "Authorization: Bearer $GITHUB_TOKEN" | jq '.workflow_runs[] | {name, status, conclusion, created_at}'
```

## Troubleshooting

| Errore | Causa | Fix |
|--------|-------|-----|
| `401 unauthorized` su `/api/v1/*` | API key revocata / istanza resettata | Rigenera key da UI Settings→API |
| `404` su `actions/workflows/*/dispatches` | Nome file workflow GHA errato o repo sbagliato | Verifica file esista in `.github/workflows/` |
| `403 Resource not accessible by integration` | PAT senza scope `repo` o token scaduto | Rigenera PAT, aggiorna credential n8n |
| `400` import workflow | Schema n8n cambiato dopo update istanza | Confronta con `GET /api/v1/workflows/{id}` di uno esistente |
| Webhook 03 risponde ma deploy non parte | `ref` errato | Body deve essere `{"ref": "main"}` |
