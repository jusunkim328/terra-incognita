#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"
if [ -f "$ENV_FILE" ]; then
  set -a; source "$ENV_FILE"; set +a
fi

ES_URL="${ES_URL:?ES_URL is required. Set it in .env}"
ES_API_KEY="${ES_API_KEY:?ES_API_KEY is required. Set it in .env}"

echo "=== Terra Incognita Alias Setup ==="
echo "ES_URL: ${ES_URL}"
echo ""

echo -n "Creating aliases (ti-papers_all, ti-papers_before_2020) ... "
http_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${ES_URL}/_aliases" \
  -H "Content-Type: application/json" \
  -H "Authorization: ApiKey ${ES_API_KEY}" \
  -d '{
    "actions": [
      { "add": { "index": "ti-papers", "alias": "ti-papers_all" } },
      {
        "add": {
          "index": "ti-papers",
          "alias": "ti-papers_before_2020",
          "filter": { "range": { "published": { "lt": "2020-01-01" } } }
        }
      }
    ]
  }')

if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
  echo "OK ($http_code)"
else
  echo "FAILED ($http_code)"
  curl -s -X POST "${ES_URL}/_aliases" \
    -H "Content-Type: application/json" \
    -H "Authorization: ApiKey ${ES_API_KEY}" \
    -d '{
      "actions": [
        { "add": { "index": "ti-papers", "alias": "ti-papers_all" } },
        {
          "add": {
            "index": "ti-papers",
            "alias": "ti-papers_before_2020",
            "filter": { "range": { "published": { "lt": "2020-01-01" } } }
          }
        }
      ]
    }'
  echo ""
  exit 1
fi

echo ""
echo "Aliases created:"
echo "  ti-papers_all          → ti-papers (no filter)"
echo "  ti-papers_before_2020  → ti-papers (published < 2020-01-01)"
