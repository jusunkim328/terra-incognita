#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"
if [ -f "$ENV_FILE" ]; then set -a; source "$ENV_FILE"; set +a; fi
KIBANA_URL="${KIBANA_URL:?KIBANA_URL is required}"
ES_API_KEY="${ES_API_KEY:?ES_API_KEY is required}"
DASHBOARD_FILE="${SCRIPT_DIR}/../dashboard/terra-incognita-dashboard.ndjson"

echo "=== Terra Incognita Dashboard Import ==="
echo "Kibana: ${KIBANA_URL}"
echo ""

http_code=$(curl -s -o /tmp/dashboard_import.json -w "%{http_code}" \
  -X POST "${KIBANA_URL}/api/saved_objects/_import?overwrite=true" \
  -H "Authorization: ApiKey ${ES_API_KEY}" \
  -H "kbn-xsrf: true" \
  -F file=@"${DASHBOARD_FILE}")

if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
  echo "Dashboard imported successfully ($http_code)"
else
  echo "FAILED ($http_code)"
  cat /tmp/dashboard_import.json | head -10
  exit 1
fi
