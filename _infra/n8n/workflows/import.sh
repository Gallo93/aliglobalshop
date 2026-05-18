#!/usr/bin/env bash
# Import & activate dei 5 workflow n8n su istanza Railway.
# Richiede:
#   N8N_BASE_URL  es. https://aliglobalshop-production.up.railway.app
#   N8N_API_KEY   API key valida (settings/api)
# Opzionale:
#   WORKFLOWS_DIR (default: dir dello script)

set -euo pipefail

: "${N8N_BASE_URL:?N8N_BASE_URL non settata}"
: "${N8N_API_KEY:?N8N_API_KEY non settata}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKFLOWS_DIR="${WORKFLOWS_DIR:-$SCRIPT_DIR}"

command -v jq >/dev/null 2>&1 || { echo "[ERROR] jq non installato" >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "[ERROR] curl non installato" >&2; exit 1; }

printf '%-42s | %-26s | %s\n' "FILE" "WORKFLOW ID" "ACTIVE"
printf -- '------------------------------------------ | -------------------------- | ------\n'

for f in "$WORKFLOWS_DIR"/0[1-5]_*.json; do
  fname="$(basename "$f")"

  resp="$(curl -sS -X POST "$N8N_BASE_URL/api/v1/workflows" \
    -H "X-N8N-API-KEY: $N8N_API_KEY" \
    -H "Content-Type: application/json" \
    --data @"$f")"

  wf_id="$(printf '%s' "$resp" | jq -r '.id // empty')"
  if [ -z "$wf_id" ]; then
    echo "[ERROR] import fallito per $fname: $resp" >&2
    continue
  fi

  act_resp="$(curl -sS -X POST "$N8N_BASE_URL/api/v1/workflows/$wf_id/activate" \
    -H "X-N8N-API-KEY: $N8N_API_KEY")"
  active="$(printf '%s' "$act_resp" | jq -r '.active // false')"

  printf '%-42s | %-26s | %s\n' "$fname" "$wf_id" "$active"
done

echo
echo "Done. Verifica con:"
echo "  curl -sS '$N8N_BASE_URL/api/v1/workflows?active=true' -H 'X-N8N-API-KEY: \$N8N_API_KEY' | jq '.data[] | {id, name, active}'"
