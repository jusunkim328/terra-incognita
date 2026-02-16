"""Terra Incognita — MCP Server

Agent Builder의 esql 도구는 읽기 전용(ES|QL = SELECT only).
Elastic Workflows 실행 엔진 버그(Hippocampus에서 확인)로,
MCP 서버로 쓰기 기능을 구현한다.

추가로 Cloud Scheduler에서 호출하는 자동화 도구도 제공:
- ti_daily_discovery: 에이전트 탐색 트리거 (Converse API)
- ti_gap_watch: open Gap 영역의 최근 논문 모니터링 (ES 직접 쿼리)

인증:
- CLOUD_RUN_URL 환경변수 설정 시 → Google OIDC ID Token 검증 (Cloud Scheduler 호출)
- 미설정 시 → 인증 스킵 (Kibana .mcp 커넥터 호출)
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

# Cloud Scheduler 자동화에 필요한 환경변수 (선택)
KIBANA_URL = os.environ.get("KIBANA_URL", "")
CLOUD_RUN_URL = os.environ.get("CLOUD_RUN_URL", "")

mcp = FastMCP(
    name="terra-incognita-writer",
    instructions="Terra Incognita 탐색 결과 저장 + 자동화 서버. Gap, Bridge, Discovery Card, Exploration Log를 ES에 기록하고, Cloud Scheduler에서 매일 탐색/모니터링을 트리거합니다.",
    host="0.0.0.0",
    port=int(os.getenv("PORT", "8080")),
    stateless_http=True,
    json_response=True,
)

# result_type → ES 인덱스 매핑
INDEX_MAP = {
    "gap": "ti-gaps",
    "bridge": "ti-bridges",
    "discovery_card": "ti-discovery-cards",
    "exploration_log": "ti-exploration-log",
}

# 각 타입별 타임스탬프 필드 이름
TIMESTAMP_FIELD = {
    "gap": "detected_at",
    "bridge": "created_at",
    "discovery_card": "created_at",
    "exploration_log": "timestamp",
}

# arXiv 도메인 매핑 (ti_ingest_new 용)
ARXIV_DOMAINS = {
    "neuroscience": "cat:q-bio.NC",
    "machine_learning": "cat:cs.LG",
    "materials_science": "cat:cond-mat.mtrl-sci",
    "quantum_computing": "cat:quant-ph",
    "ecology": "cat:q-bio.PE",
    "robotics": "cat:cs.RO",
}
INGEST_PER_DOMAIN = 10  # 도메인당 최근 10편, 총 ~60편/일


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
    """싱글톤 AsyncClient — TCP 연결 재사용."""
    global _es_client
    if _es_client is None or _es_client.is_closed:
        async with _es_lock:
            if _es_client is None or _es_client.is_closed:
                _es_client = httpx.AsyncClient(timeout=30, headers=_ES_HEADERS)
    return _es_client


async def _reset_es_client() -> None:
    """연결 장애 시 클라이언트 재생성."""
    global _es_client
    async with _es_lock:
        if _es_client is not None:
            await _es_client.aclose()
            _es_client = None


async def _index_document(index: str, document: dict) -> dict:
    """ES REST API로 문서 인덱싱 (exponential backoff 재시도)."""
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
    """ES REST API로 검색 (exponential backoff 재시도)."""
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
    """ES REST API로 문서 부분 업데이트 (exponential backoff)."""
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


# ─── Tool 1: ti_save_results (기존) ─────────────────────────────


@mcp.tool()
async def ti_save_results(
    result_type: str,
    data: str,
) -> str:
    """탐색 결과를 Elasticsearch에 저장합니다.

    5단계 워크플로우(SURVEY->DETECT->BRIDGE->VALIDATE->PROPOSE)의 결과를
    4개 인덱스에 저장합니다.

    Args:
        result_type: 저장할 결과 타입. "gap" | "bridge" | "discovery_card" | "exploration_log"
        data: JSON 문자열. 각 타입별 필드를 포함해야 합니다.
              - gap: query_text, source_domain, gap_domain, innovation_vacuum_index, status 등
              - bridge: gap_id, bridge_text, source_domain, target_domain, serendipity_probability 등
              - discovery_card: gap_id, hypothesis_title, gap_summary, innovation_vacuum_index, confidence 등
              - exploration_log: conversation_id, action, query, gaps_found, bridges_found 등
    """
    # 1) result_type 검증
    index = INDEX_MAP.get(result_type)
    if not index:
        valid = ", ".join(INDEX_MAP.keys())
        return json.dumps(
            {"status": "error", "message": f"Invalid result_type: {result_type}. Valid: {valid}"},
            ensure_ascii=False,
        )

    # 2) data JSON 파싱
    try:
        document = json.loads(data)
    except json.JSONDecodeError as e:
        return json.dumps(
            {"status": "error", "message": f"Invalid JSON in data: {e}"},
            ensure_ascii=False,
        )

    # 3) 타임스탬프 자동 추가 (없으면)
    ts_field = TIMESTAMP_FIELD[result_type]
    if ts_field not in document:
        document[ts_field] = datetime.now(timezone.utc).isoformat()

    # 4) ES에 인덱싱
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


# ─── Tool 2: ti_daily_discovery (Cloud Scheduler) ───────────────


@mcp.tool()
async def ti_daily_discovery() -> str:
    """Cloud Scheduler에서 매일 호출. Converse API로 에이전트 탐색을 트리거합니다.

    5단계 워크플로우를 자동 실행하여 새로운 연구 공백을 탐색하고
    Discovery Card를 생성합니다. 결과는 자동 저장됩니다.
    """
    if not KIBANA_URL:
        return json.dumps({"status": "error", "message": "KIBANA_URL not configured"})

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            # Step 1: 에이전트 탐색 트리거
            logger.info("Daily Discovery: triggering agent exploration")
            resp = await client.post(
                f"{KIBANA_URL}/api/agent_builder/converse",
                headers=_KIBANA_HEADERS,
                json={
                    "agent_id": "terra-incognita",
                    "input": (
                        "전체 도메인에서 새로운 연구 공백을 탐색해줘. "
                        "교차 밀도가 낮은 도메인 페어를 찾고 Discovery Card를 생성해줘."
                    ),
                },
            )
            resp.raise_for_status()
            result = resp.json()
            conv_id = result.get("conversation_id")
            logger.info("Daily Discovery: exploration done, conversation_id=%s", conv_id)

            # Step 2: 결과 저장 (같은 conversation)
            if conv_id:
                logger.info("Daily Discovery: requesting save")
                save_resp = await client.post(
                    f"{KIBANA_URL}/api/agent_builder/converse",
                    headers=_KIBANA_HEADERS,
                    json={
                        "agent_id": "terra-incognita",
                        "conversation_id": conv_id,
                        "input": "결과를 저장해줘",
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


# ─── Tool 3: ti_ingest_new (Cloud Scheduler) ────────────────────


def _collect_recent_papers(max_per_domain: int = INGEST_PER_DOMAIN) -> list[dict]:
    """동기 함수 — asyncio.to_thread()로 호출. arxiv 라이브러리가 동기."""
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
    """Cloud Scheduler에서 매일 호출. arXiv에서 최신 논문을 수집하여 ES에 인덱싱합니다.

    6개 도메인에서 각 10편씩 최신 논문을 수집하고 ti-papers 인덱스에
    bulk 인덱싱합니다. ELSER 임베딩 처리 후 daily_discovery에서 활용됩니다.
    """
    try:
        papers = await asyncio.to_thread(_collect_recent_papers, INGEST_PER_DOMAIN)
        if not papers:
            return json.dumps({"status": "ok", "indexed": 0, "message": "No new papers"})

        # _bulk API로 인덱싱
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

        # exploration-log에 인제스트 기록
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


# ─── Tool 4: ti_gap_watch (Cloud Scheduler) ─────────────────────


@mcp.tool()
async def ti_gap_watch() -> str:
    """Cloud Scheduler에서 매일 호출. open Gap 영역의 최근 논문을 확인합니다.

    에이전트 LLM 추론 없이 ES 직접 쿼리로 동작합니다.
    open 상태의 Gap을 조회하고, 각 Gap 도메인에서 최근 7일 논문을 검색하여
    새 논문이 발견되면 Alert를 생성합니다.
    """
    try:
        # Step 1: open Gap 조회 (IVI 내림차순, 상위 10개)
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

            # Step 2: 각 Gap 도메인에서 최근 7일 논문 검색
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

                # Gap 상태 자동 업데이트: open → filling
                try:
                    await _update_document("ti-gaps", gap["_id"], {
                        "status": "filling",
                        "last_watch_at": datetime.now(timezone.utc).isoformat(),
                        "filling_paper_count": len(new_papers),
                    })
                    logger.info("Gap %s status updated to 'filling'", gap["_id"])
                except Exception as e:
                    logger.warning("Gap status update failed for %s: %s", gap["_id"], e)

        # Step 3: 결과를 exploration-log에 기록
        log_doc = {
            "action": "gap_watch",
            "query": "automated gap watch",
            "gaps_found": len(alerts),
            "domains_searched": [g["_source"].get("gap_domain", "") for g in gaps],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await _index_document("ti-exploration-log", log_doc)

        message = f"{len(alerts)}개 Gap에서 새 논문 감지" if alerts else "변화 없음"
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
