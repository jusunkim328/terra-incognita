#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
# 08-mcp-save.sh
#
# Registers ti-save-results tool as MCP-based.
#
# Background: Agent Builder's esql tools are read-only (ES|QL = SELECT only).
#             Elastic Workflows execution engine bug (confirmed in Hippocampus).
#             MCP server implements write functionality for 4 indices.
#
# Prerequisites:
#   - MCP server must be deployed and accessible via HTTPS URL
#   - MCP_SERVER_URL must be set in .env
# ──────────────────────────────────────────────────────────────────
set -euo pipefail

cleanup() { rm -f /tmp/ti_mcp_tool_response.json; }
trap cleanup EXIT

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"
if [ -f "$ENV_FILE" ]; then
  set -a; source "$ENV_FILE"; set +a
fi

KIBANA_URL="${KIBANA_URL:?KIBANA_URL is required. Set it in .env}"
ES_API_KEY="${ES_API_KEY:?ES_API_KEY is required. Set it in .env}"
MCP_SERVER_URL="${MCP_SERVER_URL:?MCP_SERVER_URL is required. Set it in .env (e.g. https://your-mcp-server.run.app/mcp)}"

echo "=== Terra Incognita Save Tool (MCP) ==="
echo "Kibana:     ${KIBANA_URL}"
echo "MCP Server: ${MCP_SERVER_URL}"
echo ""

# ─── Step 1: Remove old tool (if exists) ───
echo -n "Removing old save tool (if exists) ... "
old_http=$(curl -s -o /dev/null -w "%{http_code}" \
  -X DELETE "${KIBANA_URL}/api/agent_builder/tools/ti-save-results" \
  -H "Authorization: ApiKey ${ES_API_KEY}" \
  -H "kbn-xsrf: true" \
  -H "x-elastic-internal-origin: Kibana")

if [ "$old_http" -eq 200 ]; then
  echo "REMOVED"
elif [ "$old_http" -eq 404 ]; then
  echo "NOT FOUND (ok)"
else
  echo "HTTP $old_http (continuing)"
fi

# ─── Step 2: Create .mcp connector (idempotent) ───
echo -n "Creating MCP connector ... "

CONNECTOR_JSON=$(cat <<EOF
{
  "connector_type_id": ".mcp",
  "name": "terra-incognita-writer",
  "config": { "serverUrl": "${MCP_SERVER_URL}" },
  "secrets": {}
}
EOF
)

CONNECTOR_RESPONSE=$(curl -s -w "\n%{http_code}" \
  -X POST "${KIBANA_URL}/api/actions/connector" \
  -H "Content-Type: application/json" \
  -H "Authorization: ApiKey ${ES_API_KEY}" \
  -H "kbn-xsrf: true" \
  -H "x-elastic-internal-origin: Kibana" \
  -d "${CONNECTOR_JSON}")

CONNECTOR_HTTP=$(echo "$CONNECTOR_RESPONSE" | tail -1)
CONNECTOR_BODY=$(echo "$CONNECTOR_RESPONSE" | sed '$d')

if [ "$CONNECTOR_HTTP" -ge 200 ] && [ "$CONNECTOR_HTTP" -lt 300 ]; then
  CONNECTOR_ID=$(echo "$CONNECTOR_BODY" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
  echo "OK (id: ${CONNECTOR_ID})"
elif [ "$CONNECTOR_HTTP" -eq 409 ]; then
  # Already exists — find existing connector
  echo "ALREADY EXISTS — finding existing..."
  CONNECTOR_ID=$(curl -s "${KIBANA_URL}/api/actions/connectors" \
    -H "Authorization: ApiKey ${ES_API_KEY}" \
    -H "kbn-xsrf: true" \
    -H "x-elastic-internal-origin: Kibana" \
    | python3 -c "
import json, sys
connectors = json.load(sys.stdin)
for c in connectors:
    if c.get('name') == 'terra-incognita-writer' and c.get('connector_type_id') == '.mcp':
        print(c['id'])
        break
")
  echo "  Found connector: ${CONNECTOR_ID}"
else
  echo "FAILED (HTTP ${CONNECTOR_HTTP})"
  echo "$CONNECTOR_BODY" | python3 -m json.tool 2>/dev/null || echo "$CONNECTOR_BODY"
  exit 1
fi

# ─── Step 3: Register MCP-based save tool ───
echo -n "Registering ti-save-results (MCP) ... "

TOOL_JSON=$(cat <<EOF
{
  "id": "ti-save-results",
  "type": "mcp",
  "description": "Saves exploration results to Elasticsearch. result_type: gap | bridge | discovery_card | exploration_log. data: JSON string with type-specific fields. Used when the user requests to save results.",
  "tags": ["terra-incognita", "save"],
  "configuration": {
    "connector_id": "${CONNECTOR_ID}",
    "tool_name": "ti_save_results"
  }
}
EOF
)

TOOL_HTTP=$(curl -s -o /tmp/ti_mcp_tool_response.json -w "%{http_code}" \
  -X POST "${KIBANA_URL}/api/agent_builder/tools" \
  -H "Content-Type: application/json" \
  -H "Authorization: ApiKey ${ES_API_KEY}" \
  -H "kbn-xsrf: true" \
  -H "x-elastic-internal-origin: Kibana" \
  -d "${TOOL_JSON}")

if [ "$TOOL_HTTP" -ge 200 ] && [ "$TOOL_HTTP" -lt 300 ]; then
  echo "OK ($TOOL_HTTP)"
elif [ "$TOOL_HTTP" -eq 409 ]; then
  echo "ALREADY EXISTS (409) — skipped"
elif [ "$TOOL_HTTP" -eq 400 ]; then
  echo "FAILED (400 — bad request)"
  python3 -c "import json; d=json.load(open('/tmp/ti_mcp_tool_response.json')); print('  Error:', json.dumps(d, indent=2, ensure_ascii=False)[:300])" 2>/dev/null || true
  exit 1
else
  echo "FAILED ($TOOL_HTTP)"
  python3 -c "import json; d=json.load(open('/tmp/ti_mcp_tool_response.json')); print('  Error:', json.dumps(d, indent=2, ensure_ascii=False)[:300])" 2>/dev/null || true
  exit 1
fi

echo ""
echo "Done! ti-save-results is now MCP-based."
echo "  Connector: ${CONNECTOR_ID} → ${MCP_SERVER_URL}"
echo "  Tool:      ti-save-results (type: mcp, tool: ti_save_results)"
