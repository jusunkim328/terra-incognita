#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"
if [ -f "$ENV_FILE" ]; then
  set -a; source "$ENV_FILE"; set +a
fi

ES_URL="${ES_URL:?ES_URL is required. Set it in .env}"
ES_API_KEY="${ES_API_KEY:?ES_API_KEY is required. Set it in .env}"
INGEST_DIR="${SCRIPT_DIR}/../ingest"

CHUNK_LINES=1000  # 500 docs × 2 lines (action + source)

bulk_ingest() {
  local file="$1"
  local label="$2"
  local total_lines
  total_lines=$(wc -l < "$file" | tr -d ' ')
  local total_docs=$((total_lines / 2))

  echo "=== Ingesting ${label} ==="
  echo "File: ${file}"
  echo "Total: ${total_docs} documents (${total_lines} lines)"
  echo ""

  # Pre-split into chunks for efficient processing
  local tmp_dir
  tmp_dir=$(mktemp -d)
  trap "rm -rf ${tmp_dir}" RETURN

  split -l "$CHUNK_LINES" "$file" "${tmp_dir}/chunk_"

  local chunk=1
  local errors=0
  local docs_done=0

  for chunk_file in "${tmp_dir}"/chunk_*; do
    local chunk_lines_count
    chunk_lines_count=$(wc -l < "$chunk_file" | tr -d ' ')
    local doc_count=$((chunk_lines_count / 2))

    echo -n "  Chunk ${chunk}: docs $((docs_done + 1))-$((docs_done + doc_count)) ... "

    local response
    response=$(curl -s -X POST "${ES_URL}/_bulk" \
      -H "Content-Type: application/x-ndjson" \
      -H "Authorization: ApiKey ${ES_API_KEY}" \
      --data-binary @"${chunk_file}")

    local has_errors
    has_errors=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('errors', True))" 2>/dev/null || echo "true")

    if [ "$has_errors" = "False" ]; then
      local took
      took=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('took', '?'))" 2>/dev/null || echo "?")
      echo "OK (${took}ms)"
    else
      echo "HAS ERRORS"
      echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for item in data.get('items', []):
  for op, result in item.items():
    if result.get('status', 200) >= 400:
      print(f\"  Error: {result.get('error', {}).get('type', '?')}: {result.get('error', {}).get('reason', '?')[:120]}\")
      break
" 2>/dev/null | head -5
      ((errors++))
    fi

    docs_done=$((docs_done + doc_count))
    chunk=$((chunk + 1))
  done

  echo ""
  if [ "$errors" -gt 0 ]; then
    echo "${label}: Completed with ${errors} chunk error(s)."
  else
    echo "${label}: All ${total_docs} documents ingested successfully."
  fi
  echo ""
  return $errors
}

echo "=== Terra Incognita Data Ingestion ==="
echo "ES_URL: ${ES_URL}"
echo ""

TOTAL_ERRORS=0

bulk_ingest "${INGEST_DIR}/papers.ndjson" "Recent papers" || ((TOTAL_ERRORS++))
bulk_ingest "${INGEST_DIR}/papers_before_2020.ndjson" "Pre-2020 papers (backtest)" || ((TOTAL_ERRORS++))

echo "=== Summary ==="
if [ "$TOTAL_ERRORS" -gt 0 ]; then
  echo "Completed with ${TOTAL_ERRORS} file(s) having errors."
  exit 1
else
  echo "All data ingested successfully."
fi
