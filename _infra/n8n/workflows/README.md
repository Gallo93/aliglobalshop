# n8n Workflows — AliGlobalShop

Tutti i workflow dispatchano un GitHub Actions workflow nel repo `Gallo93/aliglobalshop`.

| # | Workflow | Trigger | GitHub Action | Note |
|---|----------|---------|---------------|------|
| 01 | Fetch Products Daily | cron `0 1 * * *` (02:00 Europe/Rome) | `fetch_products.yml` | Aggiorna `_data/products/en/*.json` |
| 02 | Update Prices (6h) | cron `0 */6 * * *` | `update_prices.yml` | Aggiorna prezzi + Resend alert |
| 03 | Build Site (webhook) | webhook POST `/webhook/build-site` | `deploy.yml` | Rebuild site on demand |
| 04 | Flash Sale (hourly) | cron `0 * * * *` | `flash_sale.yml` | Aggiorna `_data/flash-sale/en.json` |
| 05 | Fetch Coupons Daily | cron `0 5 * * *` (06:00 Europe/Rome) | `fetch_coupons.yml` | Aggiorna `_data/coupons/en.json` |

## Import

```bash
for f in _infra/n8n/workflows/*.json; do
  curl -X POST "https://aliglobalshop-production.up.railway.app/api/v1/workflows" \
    -H "X-N8N-API-KEY: $N8N_API_KEY" \
    -H "Content-Type: application/json" \
    --data @"$f"
done
```

Dopo l'import, attivare ogni workflow con:
```bash
curl -X POST "$URL/api/v1/workflows/{id}/activate" -H "X-N8N-API-KEY: $N8N_API_KEY"
```

## Env vars richieste su Railway (per workflow n8n)

- `GITHUB_TOKEN` — PAT con scope `repo` e `workflow` per `Gallo93/aliglobalshop`. Usato nei nodi HTTP Request come `Bearer {{$env.GITHUB_TOKEN}}`.
