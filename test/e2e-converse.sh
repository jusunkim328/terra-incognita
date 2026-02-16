#!/usr/bin/env bash
set -euo pipefail

# Terra Incognita — E2E Converse API Test
# Sends a query to the agent and validates the 5-step workflow output.

cleanup() { rm -f /tmp/ti-e2e-request.json /tmp/ti-e2e-response.json /tmp/ti-e2e-continue.json /tmp/ti-e2e-discovery.json /tmp/ti-e2e-save.json; }
trap cleanup EXIT

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"
if [ -f "$ENV_FILE" ]; then set -a; source "$ENV_FILE"; set +a; fi

KIBANA_URL="${KIBANA_URL:?KIBANA_URL is required}"
ES_URL="${ES_URL:?ES_URL is required}"
ES_API_KEY="${ES_API_KEY:?ES_API_KEY is required}"
CURL_TIMEOUT="${CURL_TIMEOUT:-300}"

DEFAULT_QUERY="Find unexplored research directions in Alzheimer's treatment"
QUERY="${1:-$DEFAULT_QUERY}"
RESPONSE_FILE="/tmp/ti-e2e-response.json"
PASS=0
FAIL=0
TOTAL=0

# ─── Helpers ───────────────────────────────────────────────

check() {
  local label="$1" pattern="$2" file="$3"
  TOTAL=$((TOTAL + 1))
  if grep -q "$pattern" "$file" 2>/dev/null; then
    echo "  [PASS] $label"
    PASS=$((PASS + 1))
  else
    echo "  [FAIL] $label  (pattern: $pattern)"
    FAIL=$((FAIL + 1))
  fi
}

# ─── Step 1: Send initial query ────────────────────────────

echo "=== Terra Incognita E2E Test ==="
echo "Query: ${QUERY}"
echo ""

REQUEST_FILE="/tmp/ti-e2e-request.json"
python3 -c "
import json, sys
req = {'agent_id': 'terra-incognita', 'input': sys.argv[1]}
json.dump(req, open('$REQUEST_FILE', 'w'), ensure_ascii=False)
" "$QUERY"

echo "[1/3] Sending initial query..."
http_code=$(curl -s -o "$RESPONSE_FILE" -w "%{http_code}" --max-time "$CURL_TIMEOUT" \
  -X POST "${KIBANA_URL}/api/agent_builder/converse" \
  -H "Authorization: ApiKey ${ES_API_KEY}" \
  -H "kbn-xsrf: true" \
  -H "Content-Type: application/json" \
  -H "x-elastic-internal-origin: Kibana" \
  -d @"$REQUEST_FILE")

if [ "$http_code" -lt 200 ] || [ "$http_code" -ge 300 ]; then
  echo "[FATAL] Converse API returned HTTP $http_code"
  head -5 "$RESPONSE_FILE" 2>/dev/null || true
  exit 1
fi

echo "[1/3] Response received (HTTP $http_code)"

# ─── Step 2: Validate workflow steps ───────────────────────

echo ""
echo "[2/3] Validating initial response..."

check "Has conversation_id"      '"conversation_id"'  "$RESPONSE_FILE"
check "Has steps array"          '"steps"'            "$RESPONSE_FILE"
check "Has model_usage"          '"model_usage"'      "$RESPONSE_FILE"
check "Tool: ti-survey called"   'ti-survey'          "$RESPONSE_FILE"
check "Tool: ti-detect called"   'ti-detect'          "$RESPONSE_FILE"
check "Tool: ti-bridge called"   'ti-bridge'          "$RESPONSE_FILE"
check "Tool: ti-validate called" 'ti-validate'        "$RESPONSE_FILE"

# ─── Step 3: Continue to get Discovery Card ────────────────

CONV_ID=$(python3 -c "import json; print(json.load(open('$RESPONSE_FILE'))['conversation_id'])" 2>/dev/null || echo "")
RESPONSE_TEXT=$(python3 -c "import json; r=json.load(open('$RESPONSE_FILE')); print(r.get('response',{}).get('message',''))" 2>/dev/null || echo "")

# Check if Discovery Card already in response
if echo "$RESPONSE_TEXT" | grep -qi "discovery card\|Discovery Card\|Innovation Vacuum"; then
  echo ""
  echo "[3/3] Discovery Card found in initial response"
  DISCOVERY_FILE="$RESPONSE_FILE"
else
  echo ""
  echo "[3/3] Sending continuation for Discovery Card..."

  if [ -z "$CONV_ID" ]; then
    echo "  [SKIP] No conversation_id — cannot continue"
  else
    CONTINUE_FILE="/tmp/ti-e2e-continue.json"
    python3 -c "
import json
req = {'agent_id': 'terra-incognita', 'conversation_id': '$CONV_ID', 'input': 'Continue with STEP 5 PROPOSE. Generate the Discovery Card now.'}
json.dump(req, open('$CONTINUE_FILE', 'w'), ensure_ascii=False)
"
    DISCOVERY_FILE="/tmp/ti-e2e-discovery.json"
    http_code=$(curl -s -o "$DISCOVERY_FILE" -w "%{http_code}" --max-time "$CURL_TIMEOUT" \
      -X POST "${KIBANA_URL}/api/agent_builder/converse" \
      -H "Authorization: ApiKey ${ES_API_KEY}" \
      -H "kbn-xsrf: true" \
      -H "Content-Type: application/json" \
      -H "x-elastic-internal-origin: Kibana" \
      -d @"$CONTINUE_FILE")

    echo "  Continuation response (HTTP $http_code)"
  fi
fi

# Validate Discovery Card content
if [ -n "${DISCOVERY_FILE:-}" ] && [ -f "$DISCOVERY_FILE" ]; then
  FULL_TEXT=$(python3 -c "import json; r=json.load(open('$DISCOVERY_FILE')); print(r.get('response',{}).get('message',''))" 2>/dev/null || echo "")

  TOTAL=$((TOTAL + 1))
  if echo "$FULL_TEXT" | grep -qi "Discovery Card\|discovery card\|Gap\|Innovation Vacuum\|Serendipity"; then
    echo "  [PASS] Discovery Card content present"
    PASS=$((PASS + 1))
  else
    echo "  [FAIL] Discovery Card content not found"
    FAIL=$((FAIL + 1))
  fi
fi

# ─── Step 4: Save results + verify index counts ──────────

SAVE_CONV_ID="${CONV_ID:-}"
if [ -z "$SAVE_CONV_ID" ]; then
  # Get conversation_id from Discovery Card response
  SAVE_CONV_ID=$(python3 -c "import json; print(json.load(open('${DISCOVERY_FILE:-$RESPONSE_FILE}'))['conversation_id'])" 2>/dev/null || echo "")
fi

if [ -n "$SAVE_CONV_ID" ]; then
  echo ""
  echo "[4/4] Testing ti-save-results..."

  # Record doc count before save
  GAPS_BEFORE=$(curl -s --max-time 10 "${ES_URL}/ti-gaps/_count" -H "Authorization: ApiKey ${ES_API_KEY}" | python3 -c "import json,sys; print(json.load(sys.stdin)['count'])")
  LOGS_BEFORE=$(curl -s --max-time 10 "${ES_URL}/ti-exploration-log/_count" -H "Authorization: ApiKey ${ES_API_KEY}" | python3 -c "import json,sys; print(json.load(sys.stdin)['count'])")

  # Request save from agent
  SAVE_FILE="/tmp/ti-e2e-save.json"
  python3 -c "
import json
req = {'agent_id': 'terra-incognita', 'conversation_id': '$SAVE_CONV_ID', 'input': 'Save the results'}
json.dump(req, open('$SAVE_FILE', 'w'), ensure_ascii=False)
"
  save_http=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$CURL_TIMEOUT" \
    -X POST "${KIBANA_URL}/api/agent_builder/converse" \
    -H "Authorization: ApiKey ${ES_API_KEY}" \
    -H "kbn-xsrf: true" \
    -H "Content-Type: application/json" \
    -H "x-elastic-internal-origin: Kibana" \
    -d @"$SAVE_FILE")

  echo "  Save request sent (HTTP $save_http)"

  # Wait for ES to reflect changes (refresh)
  sleep 2

  # Compare doc count after save
  GAPS_AFTER=$(curl -s --max-time 10 "${ES_URL}/ti-gaps/_count" -H "Authorization: ApiKey ${ES_API_KEY}" | python3 -c "import json,sys; print(json.load(sys.stdin)['count'])")
  LOGS_AFTER=$(curl -s --max-time 10 "${ES_URL}/ti-exploration-log/_count" -H "Authorization: ApiKey ${ES_API_KEY}" | python3 -c "import json,sys; print(json.load(sys.stdin)['count'])")

  TOTAL=$((TOTAL + 1))
  if [ "$GAPS_AFTER" -gt "$GAPS_BEFORE" ] || [ "$LOGS_AFTER" -gt "$LOGS_BEFORE" ]; then
    echo "  [PASS] ti-save-results wrote data (gaps: ${GAPS_BEFORE}→${GAPS_AFTER}, logs: ${LOGS_BEFORE}→${LOGS_AFTER})"
    PASS=$((PASS + 1))
  else
    echo "  [FAIL] No new documents after save (gaps: ${GAPS_BEFORE}→${GAPS_AFTER}, logs: ${LOGS_BEFORE}→${LOGS_AFTER})"
    FAIL=$((FAIL + 1))
  fi
else
  echo ""
  echo "[4/4] [SKIP] No conversation_id — cannot test save"
fi

# ─── Summary ──────────────────────────────────────────────

echo ""
echo "=== Results: ${PASS}/${TOTAL} passed, ${FAIL} failed ==="

if [ "$FAIL" -gt 0 ]; then
  echo "STATUS: FAIL"
  exit 1
else
  echo "STATUS: PASS"
  exit 0
fi
