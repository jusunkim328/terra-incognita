#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
# 09-scheduler.sh
#
# Cloud Scheduler setup — triggers MCP server automation tools daily
#
# Job 1: ti-ingest-new (daily 08:00 KST)
#   → MCP server JSON-RPC → ti_ingest_new → collect latest arXiv papers
#
# Job 2: ti-daily-discovery (daily 09:00 KST)
#   → MCP server JSON-RPC → ti_daily_discovery → Converse API exploration
#
# Job 3: ti-gap-watch (daily 10:00 KST — 1 hour after Discovery)
#   → MCP server JSON-RPC → ti_gap_watch → direct ES query
#
# Prerequisites:
#   - MCP server must be deployed on Cloud Run
#   - MCP_SERVER_URL must be set in .env
#   - gcloud CLI must be authenticated
# ──────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"
if [ -f "$ENV_FILE" ]; then
  set -a; source "$ENV_FILE"; set +a
fi

MCP_SERVER_URL="${MCP_SERVER_URL:?MCP_SERVER_URL is required. Set it in .env}"
PROJECT_ID="${GCP_PROJECT_ID:-elastic-487512}"
REGION="${GCP_REGION:-asia-northeast3}"
SA_NAME="ti-scheduler-invoker"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
CLOUD_RUN_SERVICE="terra-incognita-mcp"

echo "=== Terra Incognita Cloud Scheduler Setup ==="
echo "MCP Server: ${MCP_SERVER_URL}"
echo "Project:    ${PROJECT_ID}"
echo "Region:     ${REGION}"
echo ""

# ─── Step 1: Create service account ───
echo -n "Creating service account (${SA_NAME}) ... "
if gcloud iam service-accounts describe "${SA_EMAIL}" --project="${PROJECT_ID}" &>/dev/null; then
  echo "ALREADY EXISTS"
else
  gcloud iam service-accounts create "${SA_NAME}" \
    --display-name="Terra Incognita Scheduler Invoker" \
    --project="${PROJECT_ID}"
  echo "OK"
fi

# ─── Step 2: Grant Cloud Run invoker role ───
echo -n "Granting Cloud Run invoker role ... "
gcloud run services add-iam-policy-binding "${CLOUD_RUN_SERVICE}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.invoker" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --quiet 2>/dev/null
echo "OK"

# ─── Step 3: Job 1 — arXiv Ingest (daily 08:00 KST — 1 hour before Discovery) ───
echo -n "Creating scheduler job: ti-ingest-new ... "
gcloud scheduler jobs delete ti-ingest-new \
  --location="${REGION}" --project="${PROJECT_ID}" --quiet 2>/dev/null || true

gcloud scheduler jobs create http ti-ingest-new \
  --schedule="0 8 * * *" \
  --time-zone="Asia/Seoul" \
  --uri="${MCP_SERVER_URL}" \
  --http-method=POST \
  --headers="Content-Type=application/json,Accept=application/json" \
  --message-body='{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"ti_ingest_new","arguments":{}}}' \
  --oidc-service-account-email="${SA_EMAIL}" \
  --oidc-token-audience="${MCP_SERVER_URL}" \
  --attempt-deadline=600s \
  --location="${REGION}" \
  --project="${PROJECT_ID}" \
  --quiet
echo "OK"

# ─── Step 4: Job 2 — Daily Discovery (daily 09:00 KST) ───
echo -n "Creating scheduler job: ti-daily-discovery ... "
# Delete existing job (if any)
gcloud scheduler jobs delete ti-daily-discovery \
  --location="${REGION}" --project="${PROJECT_ID}" --quiet 2>/dev/null || true

gcloud scheduler jobs create http ti-daily-discovery \
  --schedule="0 9 * * *" \
  --time-zone="Asia/Seoul" \
  --uri="${MCP_SERVER_URL}" \
  --http-method=POST \
  --headers="Content-Type=application/json,Accept=application/json" \
  --message-body='{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"ti_daily_discovery","arguments":{}}}' \
  --oidc-service-account-email="${SA_EMAIL}" \
  --oidc-token-audience="${MCP_SERVER_URL}" \
  --attempt-deadline=600s \
  --location="${REGION}" \
  --project="${PROJECT_ID}" \
  --quiet
echo "OK"

# ─── Step 5: Job 3 — Gap Watch (daily 10:00 KST) ───
echo -n "Creating scheduler job: ti-gap-watch ... "
# Delete existing job (if any)
gcloud scheduler jobs delete ti-gap-watch \
  --location="${REGION}" --project="${PROJECT_ID}" --quiet 2>/dev/null || true

gcloud scheduler jobs create http ti-gap-watch \
  --schedule="0 10 * * *" \
  --time-zone="Asia/Seoul" \
  --uri="${MCP_SERVER_URL}" \
  --http-method=POST \
  --headers="Content-Type=application/json,Accept=application/json" \
  --message-body='{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"ti_gap_watch","arguments":{}}}' \
  --oidc-service-account-email="${SA_EMAIL}" \
  --oidc-token-audience="${MCP_SERVER_URL}" \
  --attempt-deadline=600s \
  --location="${REGION}" \
  --project="${PROJECT_ID}" \
  --quiet
echo "OK"

echo ""
echo "Done! Cloud Scheduler jobs created:"
echo "  1. ti-ingest-new      — daily 08:00 KST → ti_ingest_new"
echo "  2. ti-daily-discovery — daily 09:00 KST → ti_daily_discovery"
echo "  3. ti-gap-watch       — daily 10:00 KST → ti_gap_watch"
echo ""
echo "Manual trigger:"
echo "  gcloud scheduler jobs run ti-ingest-new --location=${REGION}"
echo "  gcloud scheduler jobs run ti-daily-discovery --location=${REGION}"
echo "  gcloud scheduler jobs run ti-gap-watch --location=${REGION}"
echo ""
echo "View logs:"
echo "  gcloud run logs read ${CLOUD_RUN_SERVICE} --region=${REGION} --limit=50"
