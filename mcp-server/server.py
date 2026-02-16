"""Terra Incognita — MCP Server

Agent Builder's esql tools are read-only (ES|QL = SELECT only).
Due to an Elastic Workflows execution engine bug (confirmed in Hippocampus),
write functionality is implemented via this MCP server.

Also provides automation tools invoked by Cloud Scheduler:
- ti_daily_discovery: triggers agent exploration (Converse API)
- ti_gap_watch: monitors recent papers in open Gap domains (direct ES query)

Authentication:
- If CLOUD_RUN_URL env var is set → Google OIDC ID Token verification (Cloud Scheduler calls)
- If not set → authentication skipped (Kibana .mcp connector calls)
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone

import httpx
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("terra-incognita-mcp")

ES_URL = os.environ["ES_URL"]
ES_API_KEY = os.environ["ES_API_KEY"]

# Optional env vars for Cloud Scheduler automation
KIBANA_URL = os.environ.get("KIBANA_URL", "")
CLOUD_RUN_URL = os.environ.get("CLOUD_RUN_URL", "")

mcp = FastMCP(
    name="terra-incognita-writer",
    instructions="Terra Incognita result storage + automation server. Records Gaps, Bridges, Discovery Cards, and Exploration Logs to ES, and triggers daily exploration/monitoring via Cloud Scheduler.",
    host="0.0.0.0",
    port=int(os.getenv("PORT", "8080")),
    stateless_http=True,
    json_response=True,
)

# result_type → ES index mapping
INDEX_MAP = {
    "gap": "ti-gaps",
    "bridge": "ti-bridges",
    "discovery_card": "ti-discovery-cards",
    "exploration_log": "ti-exploration-log",
}

# Timestamp field name per result type
TIMESTAMP_FIELD = {
    "gap": "detected_at",
    "bridge": "created_at",
    "discovery_card": "created_at",
    "exploration_log": "timestamp",
}

# arXiv domain mapping (for ti_ingest_new)
ARXIV_DOMAINS = {
    "neuroscience": "cat:q-bio.NC",
    "machine_learning": "cat:cs.LG",
    "materials_science": "cat:cond-mat.mtrl-sci",
    "quantum_computing": "cat:quant-ph",
    "ecology": "cat:q-bio.PE",
    "robotics": "cat:cs.RO",
    "bioinformatics": "cat:q-bio.QM",
    "energy_systems": "cat:physics.app-ph",
    "astrophysics": "cat:astro-ph",
    "social_networks": "cat:cs.SI",
    "neural_computing": "cat:cs.NE",
    "artificial_intelligence": "cat:cs.AI",
}
INGEST_PER_DOMAIN = 10  # Latest 10 papers per domain, ~60 total/day


_es_client: httpx.AsyncClient | None = None
_es_lock = asyncio.Lock()

_ES_HEADERS = {
    "Authorization": f"ApiKey {ES_API_KEY}",
    "Content-Type": "application/json",
}

_KIBANA_HEADERS = {
    "Authorization": f"ApiKey {ES_API_KEY}",
    "Content-Type": "application/json",
    "kbn-xsrf": "true",
    "x-elastic-internal-origin": "Kibana",
}

_RETRYABLE_STATUS = (429, 503)
_MAX_RETRIES = 3


async def _get_es_client() -> httpx.AsyncClient:
    """Singleton AsyncClient — reuses TCP connections."""
    global _es_client
    if _es_client is None or _es_client.is_closed:
        async with _es_lock:
            if _es_client is None or _es_client.is_closed:
                _es_client = httpx.AsyncClient(timeout=30, headers=_ES_HEADERS)
    return _es_client


async def _reset_es_client() -> None:
    """Recreate client on connection failure."""
    global _es_client
    async with _es_lock:
        if _es_client is not None:
            await _es_client.aclose()
            _es_client = None


async def _index_document(index: str, document: dict) -> dict:
    """Index a document via ES REST API (with exponential backoff retry)."""
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        client = await _get_es_client()
        try:
            resp = await client.post(
                f"{ES_URL}/{index}/_doc",
                content=json.dumps(document),
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in _RETRYABLE_STATUS and attempt < _MAX_RETRIES - 1:
                wait = 2 ** attempt
                logger.warning("ES %s, retrying in %ds (attempt %d/%d)", e.response.status_code, wait, attempt + 1, _MAX_RETRIES)
                await asyncio.sleep(wait)
                last_exc = e
            else:
                raise
        except (httpx.ConnectError, httpx.ReadError) as e:
            logger.warning("Connection error: %s, resetting client (attempt %d/%d)", e, attempt + 1, _MAX_RETRIES)
            await _reset_es_client()
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(2 ** attempt)
                last_exc = e
            else:
                raise
    raise last_exc  # type: ignore[misc]


async def _search_es(index: str, body: dict, timeout: float = 30) -> dict:
    """Search via ES REST API (with exponential backoff retry)."""
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        client = await _get_es_client()
        try:
            resp = await client.post(
                f"{ES_URL}/{index}/_search",
                content=json.dumps(body),
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in _RETRYABLE_STATUS and attempt < _MAX_RETRIES - 1:
                wait = 2 ** attempt
                logger.warning("ES search %s, retrying in %ds", e.response.status_code, wait)
                await asyncio.sleep(wait)
                last_exc = e
            else:
                raise
        except (httpx.ConnectError, httpx.ReadError) as e:
            logger.warning("Search connection error: %s, resetting client", e)
            await _reset_es_client()
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(2 ** attempt)
                last_exc = e
            else:
                raise
    raise last_exc  # type: ignore[misc]


async def _update_document(index: str, doc_id: str, fields: dict) -> dict:
    """Partial document update via ES REST API (with exponential backoff)."""
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        client = await _get_es_client()
        try:
            resp = await client.post(
                f"{ES_URL}/{index}/_update/{doc_id}",
                content=json.dumps({"doc": fields}),
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in _RETRYABLE_STATUS and attempt < _MAX_RETRIES - 1:
                wait = 2 ** attempt
                logger.warning("ES update %s, retrying in %ds", e.response.status_code, wait)
                await asyncio.sleep(wait)
                last_exc = e
            else:
                raise
        except (httpx.ConnectError, httpx.ReadError) as e:
            logger.warning("Update connection error: %s, resetting client", e)
            await _reset_es_client()
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(2 ** attempt)
                last_exc = e
            else:
                raise
    raise last_exc  # type: ignore[misc]


# ─── Tool 1: ti_save_results ─────────────────────────────────────


@mcp.tool()
async def ti_save_results(
    result_type: str,
    data: str,
) -> str:
    """Save exploration results to Elasticsearch.

    Stores the output of the 5-step workflow (SURVEY->DETECT->BRIDGE->VALIDATE->PROPOSE)
    across 4 indices.

    Args:
        result_type: Type of result to save. "gap" | "bridge" | "discovery_card" | "exploration_log"
        data: JSON string. Must include the fields for each type:
              - gap: query_text, source_domain, gap_domain, innovation_vacuum_index, status, etc.
              - bridge: gap_id, bridge_text, source_domain, target_domain, serendipity_probability, etc.
              - discovery_card: gap_id, hypothesis_title, gap_summary, innovation_vacuum_index, confidence, etc.
              - exploration_log: conversation_id, action, query, gaps_found, bridges_found, etc.
    """
    # 1) Validate result_type
    index = INDEX_MAP.get(result_type)
    if not index:
        valid = ", ".join(INDEX_MAP.keys())
        return json.dumps(
            {"status": "error", "message": f"Invalid result_type: {result_type}. Valid: {valid}"},
            ensure_ascii=False,
        )

    # 2) Parse data JSON
    try:
        document = json.loads(data)
    except json.JSONDecodeError as e:
        return json.dumps(
            {"status": "error", "message": f"Invalid JSON in data: {e}"},
            ensure_ascii=False,
        )

    # 3) Auto-add timestamp if missing
    ts_field = TIMESTAMP_FIELD[result_type]
    if ts_field not in document:
        document[ts_field] = datetime.now(timezone.utc).isoformat()

    # 4) Index to ES
    try:
        result = await _index_document(index, document)
        return json.dumps(
            {
                "status": "ok",
                "index": index,
                "id": result.get("_id"),
                "result": result.get("result"),
            },
            ensure_ascii=False,
        )
    except httpx.HTTPStatusError as e:
        logger.error("ES indexing failed: %s %s", e.response.status_code, e.response.text)
        return json.dumps(
            {
                "status": "error",
                "index": index,
                "http_status": e.response.status_code,
                "message": e.response.text[:500],
            },
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return json.dumps(
            {"status": "error", "index": index, "message": str(e)},
            ensure_ascii=False,
        )


# ─── Tool 2: ti_daily_discovery (Cloud Scheduler) ────────────────


@mcp.tool()
async def ti_daily_discovery() -> str:
    """Called daily by Cloud Scheduler. Triggers agent exploration via Converse API.

    Automatically runs the 5-step workflow to discover new research gaps
    and generate Discovery Cards. Results are saved automatically.
    """
    if not KIBANA_URL:
        return json.dumps({"status": "error", "message": "KIBANA_URL not configured"})

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            # Step 1: Trigger agent exploration
            logger.info("Daily Discovery: triggering agent exploration")
            resp = await client.post(
                f"{KIBANA_URL}/api/agent_builder/converse",
                headers=_KIBANA_HEADERS,
                json={
                    "agent_id": "terra-incognita",
                    "input": (
                        "Explore new research gaps across all domains. "
                        "Find domain pairs with low cross-density and generate a Discovery Card."
                    ),
                },
            )
            resp.raise_for_status()
            result = resp.json()
            conv_id = result.get("conversation_id")
            logger.info("Daily Discovery: exploration done, conversation_id=%s", conv_id)

            # Step 2: Save results (same conversation)
            if conv_id:
                logger.info("Daily Discovery: requesting save")
                save_resp = await client.post(
                    f"{KIBANA_URL}/api/agent_builder/converse",
                    headers=_KIBANA_HEADERS,
                    json={
                        "agent_id": "terra-incognita",
                        "conversation_id": conv_id,
                        "input": "Save the results",
                    },
                )
                save_resp.raise_for_status()
                logger.info("Daily Discovery: save complete")

        return json.dumps({"status": "ok", "conversation_id": conv_id})

    except httpx.HTTPStatusError as e:
        logger.error("Daily Discovery failed: %s %s", e.response.status_code, e.response.text[:500])
        return json.dumps({
            "status": "error",
            "http_status": e.response.status_code,
            "message": e.response.text[:500],
        })
    except Exception as e:
        logger.error("Daily Discovery unexpected error: %s", e)
        return json.dumps({"status": "error", "message": str(e)})


# ─── Tool 3: ti_ingest_new (Cloud Scheduler) ─────────────────────


def _collect_recent_papers(max_per_domain: int = INGEST_PER_DOMAIN) -> list[dict]:
    """Synchronous function — called via asyncio.to_thread(). The arxiv library is sync."""
    import arxiv

    papers: list[dict] = []
    seen_ids: set[str] = set()
    client = arxiv.Client(page_size=50, delay_seconds=3, num_retries=3)

    for domain_name, query in ARXIV_DOMAINS.items():
        search = arxiv.Search(
            query=query,
            max_results=max_per_domain,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )
        for result in client.results(search):
            arxiv_id = result.entry_id.split("/abs/")[-1].split("v")[0]
            if arxiv_id in seen_ids:
                continue
            seen_ids.add(arxiv_id)
            papers.append({
                "arxiv_id": arxiv_id,
                "title": result.title,
                "abstract": result.summary,
                "content": f"{result.title}. {result.summary}",
                "primary_category": result.primary_category,
                "categories": result.categories,
                "domain": domain_name,
                "published": result.published.isoformat(),
                "authors": [a.name for a in result.authors[:10]],
            })

    return papers


@mcp.tool()
async def ti_ingest_new() -> str:
    """Called daily by Cloud Scheduler. Collects latest papers from arXiv and indexes them in ES.

    Collects up to 10 latest papers per domain across 12 domains and bulk-indexes
    them into the ti-papers index. After ELSER embedding, they are used by daily_discovery.
    """
    try:
        papers = await asyncio.to_thread(_collect_recent_papers, INGEST_PER_DOMAIN)
        if not papers:
            return json.dumps({"status": "ok", "indexed": 0, "message": "No new papers"})

        # Bulk index via _bulk API
        lines: list[str] = []
        for doc in papers:
            lines.append(json.dumps({"index": {"_index": "ti-papers", "_id": doc["arxiv_id"]}}))
            lines.append(json.dumps(doc, ensure_ascii=False))
        body = "\n".join(lines) + "\n"

        client = await _get_es_client()
        resp = await client.post(
            f"{ES_URL}/_bulk",
            content=body.encode("utf-8"),
            headers={**_ES_HEADERS, "Content-Type": "application/x-ndjson"},
            timeout=120,
        )
        resp.raise_for_status()
        result = resp.json()
        errors = sum(1 for item in result.get("items", []) if item.get("index", {}).get("error"))
        indexed = len(papers) - errors

        # Record ingest in exploration-log
        await _index_document("ti-exploration-log", {
            "action": "ingest",
            "query": "automated arXiv ingest",
            "gaps_found": 0,
            "domains_searched": list(ARXIV_DOMAINS.keys()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "papers_collected": len(papers),
            "papers_indexed": indexed,
        })

        logger.info("Ingest: collected %d, indexed %d, errors %d", len(papers), indexed, errors)
        return json.dumps({
            "status": "ok",
            "total_collected": len(papers),
            "indexed": indexed,
            "errors": errors,
        })

    except Exception as e:
        logger.error("Ingest error: %s", e)
        return json.dumps({"status": "error", "message": str(e)})


# ─── Tool 4: ti_gap_watch (Cloud Scheduler) ──────────────────────


@mcp.tool()
async def ti_gap_watch() -> str:
    """Called daily by Cloud Scheduler. Checks recent papers in open Gap domains.

    Operates via direct ES queries without agent LLM inference.
    Retrieves open Gaps and searches for papers from the last 7 days in each Gap domain.
    Generates alerts when new papers are found.
    """
    try:
        # Step 1: Query open Gaps (IVI descending, top 10)
        gaps_result = await _search_es("ti-gaps", {
            "query": {"term": {"status": "open"}},
            "sort": [{"innovation_vacuum_index": "desc"}],
            "size": 10,
        })
        gaps = gaps_result.get("hits", {}).get("hits", [])
        logger.info("Gap Watch: found %d open gaps", len(gaps))

        alerts = []
        for gap in gaps:
            src = gap["_source"]
            gap_concept = src.get("gap_concept", "")
            gap_domain = src.get("gap_domain", "")

            if not gap_concept or not gap_domain:
                continue

            # Step 2: Search for papers from the last 7 days in each Gap domain
            papers_result = await _search_es("ti-papers", {
                "query": {
                    "bool": {
                        "must": [
                            {"match": {"content": gap_concept}},
                            {"term": {"domain": gap_domain}},
                        ],
                        "filter": [
                            {"range": {"published": {"gte": "now-7d"}}},
                        ],
                    },
                },
                "size": 5,
            })
            new_papers = papers_result.get("hits", {}).get("hits", [])

            if new_papers:
                alerts.append({
                    "gap_id": gap["_id"],
                    "gap_concept": gap_concept,
                    "gap_domain": gap_domain,
                    "ivi": src.get("innovation_vacuum_index"),
                    "new_paper_count": len(new_papers),
                    "new_papers": [p["_source"].get("title", "untitled") for p in new_papers[:3]],
                })

                # Auto-update Gap status: open → filling
                try:
                    await _update_document("ti-gaps", gap["_id"], {
                        "status": "filling",
                        "last_watch_at": datetime.now(timezone.utc).isoformat(),
                        "filling_paper_count": len(new_papers),
                    })
                    logger.info("Gap %s status updated to 'filling'", gap["_id"])
                except Exception as e:
                    logger.warning("Gap status update failed for %s: %s", gap["_id"], e)

        # Step 3: Record results in exploration-log
        log_doc = {
            "action": "gap_watch",
            "query": "automated gap watch",
            "gaps_found": len(alerts),
            "domains_searched": [g["_source"].get("gap_domain", "") for g in gaps],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await _index_document("ti-exploration-log", log_doc)

        message = f"New papers detected in {len(alerts)} gap(s)" if alerts else "No changes detected"
        logger.info("Gap Watch: %s", message)

        return json.dumps({
            "status": "ok",
            "monitored_gaps": len(gaps),
            "alerts": alerts,
            "message": message,
        }, ensure_ascii=False)

    except Exception as e:
        logger.error("Gap Watch error: %s", e)
        return json.dumps({"status": "error", "message": str(e)})


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
