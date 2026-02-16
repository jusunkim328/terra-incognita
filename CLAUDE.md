# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Language

Always communicate in Korean (한국어).

## Project Overview

Terra Incognita는 Elasticsearch Agent Builder 기반의 **자율 연구 공백 탐지 에이전트**다. 과학 논문의 벡터 공간에서 연구 공백(Gap)을 찾고, 전혀 다른 분야에서 그 공백을 채울 예상치 못한 다리(Bridge)를 제안한다. 핵심 차별화: 기존 도구는 "있는 논문"을 검색하지만, Terra Incognita는 **"없는 연구"를 발견**한다.

## Hackathon Context

[Elasticsearch Agent Builder Hackathon](https://elasticsearch.devpost.com/) 출품작.

- **마감**: 2026-02-27 1:00pm EST
- **심사**: 기술 실행력 30% / 임팩트·혁신성 30% / 데모 품질 30% / 소셜 공유 10%
- **제출 요건**: ~300단어 설명 + 3분 데모 영상 + 공개 저장소(OSI 라이선스) + 선택적 소셜 포스트(@elastic_devs)
- **데이터 규칙**: 모든 데이터는 오픈소스 또는 합성(synthetic)이어야 함 — 기밀/개인정보 금지
- **필수 기술**: Elastic Workflows, Search, ES|QL 중 하나 이상 → 우리는 ES|QL 4개 도구 사용으로 충족
- **데모 스크립트**: `demo/demo-script.md` — 4막 구성
- **상세 참조**: `docs/hackathon-reference.md`

### 제출 전 체크리스트

- [ ] GitHub repo **public** 전환
- [x] **LICENSE** 파일 추가 (MIT)
- [x] `.env`는 `.env.example`만 포함 (실제 credential 제외 — `.gitignore`에 `.env` 있음)
- [x] seed data가 **synthetic**임을 README에 명시
- [x] ~300단어 설명 작성 (`demo/devpost-description.md`)
- [ ] 3분 데모 영상 제작
- [x] 소셜 미디어 포스트 (`demo/social-post.md`)

## Setup & Deployment

```bash
# Prerequisites: Elastic Cloud Hosted (ES 9.x), ELSER v2 deployed, Agent Builder enabled
# Copy .env.example to .env and fill in ES_URL, ES_API_KEY, KIBANA_URL, MCP_SERVER_URL

# 1. MCP 서버 배포 (Docker) — save 도구의 백엔드
docker build -t ti-mcp-server mcp-server/
# 배포 후 HTTPS URL을 .env의 MCP_SERVER_URL에 설정

# 2. Deploy in order (each script depends on the previous)
bash setup/01-indices.sh      # 5 ES indices (ES API)
bash setup/02-aliases.sh      # Backtest aliases (ES API)
bash setup/03-tools.sh        # 4 ES|QL Agent Builder tools (Kibana API)
bash setup/08-mcp-save.sh     # MCP connector + save tool (Kibana API)
bash setup/04-agent.sh        # 1 agent (Kibana API)
bash setup/05-ingest.sh       # Paper data (ES API)
bash setup/06-seed-data.sh    # Seed data via _bulk (ES API)
bash setup/07-dashboard.sh    # Dashboard import (Kibana API)
```

### Setup 스크립트 상세

| 순서 | 스크립트 | 대상 API | 역할 |
|------|---------|----------|------|
| 1 | `01-indices.sh` | ES | 5개 인덱스 생성 |
| 2 | `02-aliases.sh` | ES | 백테스트 alias 2개 |
| 3 | `03-tools.sh` | Kibana | ES\|QL 도구 4개 등록 |
| 4 | `08-mcp-save.sh` | Kibana | .mcp 커넥터 + save 도구 등록 |
| 5 | `04-agent.sh` | Kibana | 에이전트 등록 (tool_ids 의존) |
| 6 | `05-ingest.sh` | ES | 논문 데이터 bulk indexing |
| 7 | `06-seed-data.sh` | ES | 합성 seed data import |
| 8 | `07-dashboard.sh` | Kibana | 대시보드 NDJSON import |
| 9 | `09-scheduler.sh` | GCP | Cloud Scheduler 3개 잡 설정 |

Scripts 01-02, 05-06 target `ES_URL`. Scripts 03-04, 07-08 target `KIBANA_URL`. Both use `ES_API_KEY` for auth. Kibana API requires `kbn-xsrf: true` header.

**순서 주의**: `08-mcp-save.sh`는 반드시 `04-agent.sh` **이전**에 실행 — agent의 `tool_ids`에 `ti-save-results`가 포함되어 있으므로 도구가 먼저 존재해야 함.

### Redeployment (도구/에이전트 변경 시)

Kibana Agent Builder API는 POST로 이미 존재하는 리소스를 생성하면 400/409 반환. **삭제 후 재생성** 필요:

```bash
export $(cat .env | xargs)

# 도구 삭제 + 재등록
for tool in ti-survey ti-detect ti-bridge ti-validate ti-save-results; do
  curl -X DELETE "${KIBANA_URL}/api/agent_builder/tools/${tool}" \
    -H "Authorization: ApiKey ${ES_API_KEY}" -H "kbn-xsrf: true" -H "x-elastic-internal-origin: Kibana"
done
bash setup/03-tools.sh
bash setup/08-mcp-save.sh

# 에이전트 삭제 + 재등록
curl -X DELETE "${KIBANA_URL}/api/agent_builder/agents/terra-incognita" \
  -H "Authorization: ApiKey ${ES_API_KEY}" -H "kbn-xsrf: true" -H "x-elastic-internal-origin: Kibana"
bash setup/04-agent.sh
```

## Architecture

### 5-Step Workflow

```
Query → STEP 1: SURVEY (ti-survey)
      → STEP 2: DETECT (ti-detect) + 파라미터 자율 조정
      → STEP 3: BRIDGE (ti-bridge) + Self-Correction
      → STEP 4: VALIDATE (ti-validate) + cross-list 확인
      → STEP 5: PROPOSE (가설 생성 + Discovery Card)
```

### Data Model

- **ti-papers**: 논문 코퍼스, `semantic_text` (ELSER `.elser-2-elastic`), 6 도메인 × 1,000편
- **ti-gaps**: 탐지된 연구 공백, Innovation Vacuum Index + 퍼센타일
- **ti-bridges**: 교차 분야 다리, Serendipity Probability + 신뢰도
- **ti-exploration-log**: 탐색 감사 로그, Thought Log, Self-Correction 횟수
- **ti-discovery-cards**: 소셜 공유용 Discovery Card

### Backtest Aliases

- `ti-papers_before_2020`: 2020년 이전 데이터만 — 백테스트 탐색용
- `ti-papers_all`: 전체 데이터 — 검증용
- 프레이밍: "당시 데이터로 교차 신호가 잡혔고, 이후 실제로 교차 논문이 등장했다"

### Two API Surfaces

| Component | API | Base URL | Headers |
|-----------|-----|----------|---------|
| Indices, Aliases, Bulk data | Elasticsearch REST API | `ES_URL` | `Authorization: ApiKey` |
| Tools, Agents, Dashboard | Kibana API | `KIBANA_URL` | `Authorization: ApiKey` + `kbn-xsrf: true` + `x-elastic-internal-origin: Kibana` |

Kibana URL has a **different subdomain** from ES URL.

### Agent Builder 도구 (5개 커스텀 + 2개 플랫폼)

| 도구 | 타입 | 역할 |
|------|------|------|
| `ti-survey` | esql | STEP 1 — 전 도메인 관련도 프로필링 |
| `ti-detect` | esql | STEP 2 — Gap 탐지 + 밀도 분석 + IVI 계산 |
| `ti-bridge` | esql | STEP 3 — RRF 교차 분야 다리 탐색 |
| `ti-validate` | esql | STEP 4 — 참신성 검증 (교차 논문 카운트) |
| `ti-save-results` | mcp | 결과 저장 — 4개 인덱스에 쓰기 (MCP 서버 경유) |
| `platform.core.execute_esql` | 내장 | 백테스트 모드 등 ad-hoc 쿼리 |
| `platform.core.search` | 내장 | 인덱스 검색 (검증) |

### MCP 서버 (`mcp-server/`)

결과 저장 + Cloud Scheduler 자동화의 백엔드. Agent Builder의 esql 도구는 읽기 전용이고, Elastic Workflows 실행 엔진 버그로 MCP 서버 사용.

- **스택**: FastMCP 1.9+, Streamable HTTP transport, Python 3.12, httpx (async)
- **도구 5개**:
  - `ti_save_results(result_type, data)` — 결과 저장, result_type으로 4개 인덱스 분기
  - `ti_daily_discovery()` — Cloud Scheduler 호출, Converse API로 에이전트 탐색 트리거
  - `ti_gap_watch()` — Cloud Scheduler 호출, open Gap의 최근 논문 ES 직접 쿼리
  - `ti_ingest_new()` — Cloud Scheduler 호출, arXiv 최신 논문 수집 + ES 인덱싱
  - `_update_document(index, doc_id, doc)` — 내부 헬퍼, Gap 상태 업데이트 등에 사용
- **동작**: ES REST API로 4개 인덱스에 직접 쓰기 + Kibana Converse API로 에이전트 트리거
- **배포**: Cloud Run (`docker build -t ti-mcp-server mcp-server/` → HTTPS 엔드포인트)
- **환경변수**: `ES_URL`, `ES_API_KEY`, `KIBANA_URL` (자동화용), `CLOUD_RUN_URL` (OIDC 검증용, 선택), `PORT` (기본 8080), `LOG_LEVEL` (기본 INFO)
- `.mcp` Kibana 커넥터 → Agent Builder `mcp` 타입 도구로 연결
- `MCP_SERVER_URL`이 .env에 없을 경우, 기존 커넥터 ID를 `GET /api/actions/connectors`로 조회 가능

**인덱스 매핑 + 타임스탬프**:

| result_type | 인덱스 | 타임스탬프 필드 |
|-------------|--------|----------------|
| `gap` | ti-gaps | `detected_at` |
| `bridge` | ti-bridges | `created_at` |
| `discovery_card` | ti-discovery-cards | `created_at` |
| `exploration_log` | ti-exploration-log | `timestamp` |

타임스탬프가 data에 없으면 서버가 UTC ISO 형식으로 자동 추가.

**내결함성**: httpx.AsyncClient 싱글톤 (double-checked locking) + ES 429/503에 exponential backoff (최대 3회) + ConnectError/ReadError 시 클라이언트 자동 재생성.

### Cloud Scheduler (자동화)

MCP 서버의 자동화 도구를 Cloud Scheduler가 매일 JSON-RPC로 호출:

```
Cloud Scheduler (cron)
  → OIDC auth
  → Cloud Run MCP 서버 POST /mcp
  → JSON-RPC: tools/call { name: "ti_ingest_new" | "ti_daily_discovery" | "ti_gap_watch" }
```

| Job | 스케줄 | MCP 도구 | 동작 |
|-----|--------|----------|------|
| `ti-ingest-new` | 매일 08:00 KST | `ti_ingest_new` | arXiv 최신 논문 수집 |
| `ti-daily-discovery` | 매일 09:00 KST | `ti_daily_discovery` | Converse API로 에이전트 탐색 + 자동 저장 |
| `ti-gap-watch` | 매일 10:00 KST | `ti_gap_watch` | open Gap의 최근 7일 논문 ES 직접 조회 |

**타임아웃 체인**: Cloud Scheduler 600s → Cloud Run 600s → Converse API 180s × 2

**설정**: `bash setup/09-scheduler.sh` — 서비스 계정 생성 + OIDC 권한 + 3개 잡 생성

**수동 트리거**:
```bash
gcloud scheduler jobs run ti-ingest-new --location=asia-northeast3
gcloud scheduler jobs run ti-daily-discovery --location=asia-northeast3
gcloud scheduler jobs run ti-gap-watch --location=asia-northeast3
```

### Tool Types (Kibana Agent Builder API)

- `esql`: `configuration.query` + `configuration.params` (object, not array; empty `{}` if no params)
- `mcp`: `configuration.connector_id` + `configuration.tool_name` — `.mcp` 커넥터를 통해 외부 MCP 서버 호출
- `index_search`: `configuration.pattern` (index pattern string)

## Agent Instructions (9 Rules)

에이전트 `terra-incognita`의 instructions (`agent/ti-agent.json`)에 정의된 규칙:

| RULE | 이름 | 핵심 |
|------|------|------|
| 1 | 5단계 워크플로우 | SURVEY→DETECT→BRIDGE→VALIDATE→PROPOSE 순서 필수 (Gap Watch 요청 시 RULE 9로 분기) |
| 2 | Self-Correction | BRIDGE 단계에서 키워드만 일치하는 후보 폐기, 최대 3회 재탐색 |
| 3 | 정량 점수 체계 | IVI/SP 계산 공식 + 퍼센타일 표시 |
| 4 | 파라미터 자율 조정 | 도메인 밀집도에 따라 Gap 임계값 동적 조정, Thought Log 기록 |
| 5 | Discovery Card 형식 | 표준 템플릿 (🗺️/📊/🌉/📑/🎯) |
| 6 | 백테스트 모드 | ti-papers_before_2020 → 탐색, ti-papers_all → 검증 |
| 7 | 결과 저장 | **자동 저장 금지** — 사용자 요청 시에만 ti-save-results 호출 |
| 8 | 개인화 | STEP 1 전 exploration-log 조회(`action=="propose"`), 중복 도메인 건너뛰기, 이전 탐색 연결 |
| 9 | Gap Watch 모드 | open Gap의 최근 논문 모니터링 — Alert/Report 형식 출력 |

**Gap 상태 lifecycle**:
- `open` → `filling` (자동: Gap Watch에서 새 논문 감지 시)
- `filling` → `bridged` (향후)
- `bridged` → `validated` (향후)

**exploration-log action 값 규약**: 시드 데이터의 action 필드는 워크플로우 단계별(`survey`, `detect`, `bridge`, `validate`, `propose`)로 기록됨. RULE 7의 저장 예시는 `"action":"explore"`(범용)이나, RULE 8의 개인화 조회는 `action == "propose"`(최종 가설 제안 단계)만 필터링하여 완성된 탐색 이력만 참조함.

## 데이터 파이프라인

### arXiv 논문 수집 (`ingest/arxiv_collector.py`)

```bash
python3 ingest/arxiv_collector.py                          # 전체 수집
python3 ingest/arxiv_collector.py --before 2020            # 백테스트용
python3 ingest/arxiv_collector.py --max-per-domain 500     # 도메인당 500편
```

**6개 도메인**: neuroscience (`q-bio.NC`), machine_learning (`cs.LG`), materials_science (`cond-mat.mtrl-sci`), quantum_computing (`quant-ph`), ecology (`q-bio.PE`), robotics (`cs.RO`)

출력: `ingest/papers.ndjson` (NDJSON, `_bulk` API 형식). `content` 필드 = title + abstract (semantic_text 임베딩 대상).

### 환경변수 (`.env`)

| 변수 | 대상 | 필수 | 예시 |
|------|------|------|------|
| `ES_URL` | ES API | Yes | `https://....es.region.gcp.elastic-cloud.com:443` |
| `ES_API_KEY` | 인증 | Yes | `base64_encoded_key` |
| `KIBANA_URL` | Kibana API | Yes | `https://....kb.region.gcp.elastic-cloud.com:443` |
| `MCP_SERVER_URL` | MCP 서버 | Yes | `https://....run.app/mcp` |
| `CLOUD_RUN_URL` | OIDC 검증 | No | `https://....run.app` (Cloud Run 배포 시) |

`.env`는 `.gitignore`에 포함. `.env.example`만 커밋.

## Key Conventions

- All setup scripts source `.env` via `set -a; source "$ENV_FILE"; set +a`
- curl commands use direct `-H "Authorization: ApiKey ${ES_API_KEY}"` (no eval, macOS compatible)
- Seed data files are NDJSON with action+doc pairs for `_bulk` API
- `semantic_text` fields double the `_cat/indices` doc count (ELSER inference chunks); use `_count` API for actual count
- Agent tool validation: all `tool_ids` in agent config must exist before agent registration
- 모든 시드 데이터는 **합성(synthetic)** — 실제 또는 기밀 데이터 없음
- Shell 스크립트에서 `head -n -1`은 macOS 비호환 → `sed '$d'` 사용
- 임시 파일 생성 시 `trap cleanup EXIT` 패턴 사용

## 정량 점수 체계

### Innovation Vacuum Index (IVI)
```
IVI = (relevance × 0.3) + (void × 0.5) + (density/100 × 0.2)
```
- relevance: Gap 도메인의 avg_score (0~1)
- void: 1 - (gap_paper_count / max_paper_count) (0~1)
- density: Gap 도메인의 paper_count

### Serendipity Probability (SP)
```
SP = (similarity × 0.3) + (novelty × 0.4) + (evidence/50 × 0.3)
```
- similarity: 다리 논문의 avg _score (0~1)
- novelty: 1 - (cross_paper_count / total_in_both_domains) (0~1)
- evidence: 다리 후보 논문 수 (cap at 50)

## E2E Testing

### 자동화 테스트 스크립트

```bash
bash test/e2e-converse.sh                    # 기본 쿼리
bash test/e2e-converse.sh "양자 컴퓨팅 공백"   # 커스텀 쿼리
CURL_TIMEOUT=600 bash test/e2e-converse.sh   # 타임아웃 조정
```

**검증 항목 (4단계)**:
1. 초기 응답 — conversation_id, steps, model_usage 존재
2. 도구 호출 — ti-survey, ti-detect, ti-bridge, ti-validate 4개 모두 호출
3. Discovery Card — "Innovation Vacuum" 또는 "Serendipity" 키워드 포함
4. 저장 검증 — "결과를 저장해줘" → ti-gaps/ti-exploration-log doc count 증가

### 수동 Converse API 호출

```bash
export $(cat .env | xargs)

curl -s -X POST "${KIBANA_URL}/api/agent_builder/converse" \
  -H "Authorization: ApiKey ${ES_API_KEY}" \
  -H "kbn-xsrf: true" \
  -H "Content-Type: application/json" \
  -H "x-elastic-internal-origin: Kibana" \
  -d '{"agent_id": "terra-incognita", "input": "알츠하이머 치료에서 아직 탐험되지 않은 연구 방향을 찾아줘"}'
```

### UI 검증

Agent Builder UI 테스트는 **Playwright MCP** 사용 (Chrome DevTools MCP — SSO 이슈).

## Dashboard

6개 패널: Research Landscape, Innovation Vacuum Index Top 10, Cross-Paper Count, Serendipity Probability Ranking, Domain×Gap Heatmap, Discovery Timeline.

**주의**: 코드로 Kibana 9.x NDJSON 생성 시 `coreMigrationVersion`, `typeMigrationVersion` 호환 문제 빈발. Kibana UI에서 직접 생성 → export 권장.

### NDJSON Import

```bash
curl -X POST "${KIBANA_URL}/api/saved_objects/_import?overwrite=true" \
  -H "Authorization: ApiKey ${ES_API_KEY}" -H "kbn-xsrf: true" \
  -F file=@dashboard/terra-incognita-dashboard.ndjson
```

## Working Preferences

- 무언가의 작업을 대기할 때는 Exponential Backoff 방식으로 해
- 개발 작업할 때는 Agent Teams 사용을 항상 검토해
