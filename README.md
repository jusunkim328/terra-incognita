# Terra Incognita: Autonomous Scout for the Unknown

[![Elasticsearch](https://img.shields.io/badge/Elasticsearch-9.x-005571?logo=elasticsearch&logoColor=white)](https://www.elastic.co/elasticsearch)
[![Kibana](https://img.shields.io/badge/Kibana-9.x-005571?logo=kibana&logoColor=white)](https://www.elastic.co/kibana)
[![ELSER](https://img.shields.io/badge/ELSER-v2-00BFB3)](https://www.elastic.co/guide/en/machine-learning/current/ml-nlp-elser.html)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Existing tools search for papers that exist. Terra Incognita discovers research that doesn't exist yet.**

---

## The Problem

Every research discovery tool today — Semantic Scholar, Connected Papers, Elicit — helps you find **papers that already exist**. But scientific breakthroughs happen when two things converge:

1. **"This area is empty"** — recognizing an unexplored territory (Gap Detection)
2. **"The key is in a completely different field"** — finding an unexpected connection (Serendipity Bridge)

Penicillin = gap in bacteriology + mycology. CRISPR = gap in gene editing + bacterial immunology. Deep learning = gap in pattern recognition + neuroscience.

**No tool searches for what's missing.**

## The Solution

Terra Incognita is an **Autonomous Scout** that maps the landscape of scientific literature, identifies meaningful research gaps, and proposes cross-disciplinary bridges to fill them — complete with quantitative scoring and novelty verification.

It uses Elasticsearch's semantic search, ES|QL analytics, and Agent Builder to automate the entire discovery pipeline: from surveying 17,000+ papers across 12 domains, to detecting "meaningful voids" where research *should* exist but doesn't, to finding unexpected connections from distant fields.

---

## Architecture: 5-Step Workflow

```
[User Query: "Find unexplored research directions in neurodegenerative disease treatment"]
        |
        v
+--- 1. SURVEY ------------------------------------------------+
|  Search all domains -> collect per-domain relevance scores     |
|  ES: semantic search (ELSER v2, RRF hybrid)                   |
+----------------------------+---------------------------------+
                             |
                             v
+--- 2. DETECT ------------------------------------------------+
|  Analyze score distribution -> identify "meaningful gaps"      |
|  ES: ES|QL aggregation + density analysis                     |
|  Agent: autonomous parameter tuning                           |
+----------------------------+---------------------------------+
                             |
                             v
+--- 3. BRIDGE ------------------------------------------------+
|  Re-search remote domains using gap concepts                   |
|  ES: RRF (BM25 low + Vector high = unexpected connections)    |
|  Agent: Self-Correction (discard false positives)             |
+----------------------------+---------------------------------+
                             |
                             v
+--- 4. VALIDATE ----------------------------------------------+
|  Verify no existing papers at the intersection                 |
|  ES: ES|QL COUNT + cross-category filter + arXiv cross-list   |
+----------------------------+---------------------------------+
                             |
                             v
+--- 5. PROPOSE ------------------------------------------------+
|  Generate research hypothesis + evidence + confidence score    |
|  Agent Builder: multi-step reasoning + Discovery Card          |
+--------------------------------------------------------------+
```

Each step maps to a dedicated ES|QL tool registered in Agent Builder, enabling full traceability and explainability.

---

## Quantitative Scoring

### Innovation Vacuum Index (Gap Score)

Quantifies how "meaningfully empty" a research gap is:

```
IVI = (relevance x 0.3) + (void x 0.5) + (density/100 x 0.2)
```

| Component | Meaning | Calculation |
|-----------|---------|-------------|
| **Relevance** | Semantic relevance to query | `AVG(_score)` from semantic search |
| **Void** | Absence of cross-domain papers | `1 - (cross_papers / total_papers)` |
| **Density** | Surrounding research activity | `SUM(adjacent_domain_papers)` |

A high IVI means the gap is surrounded by active research but the intersection itself is unexplored — the most promising kind of gap.

### Serendipity Probability (Bridge Score)

Quantifies the "unexpected connection potential" of a cross-disciplinary bridge:

```
SP = (similarity x 0.3) + (novelty x 0.4) + (evidence/50 x 0.3)
```

| Component | Meaning | Calculation |
|-----------|---------|-------------|
| **Similarity** | Semantic similarity to original query | `_score` from RRF |
| **Novelty** | Absence of existing bridges | `1 - (existing_bridges / max_possible)` |
| **Evidence** | Supporting papers in bridge domain | `COUNT(*)` in bridge domain |

Both scores are displayed as **percentiles** (e.g., "top 2%") for intuitive interpretation, and all three components are exposed individually for **explainability** — the analysis engine is Elasticsearch, not a black-box LLM.

---

## Agent Autonomy

### Self-Correction Protocol

During the BRIDGE step, the agent autonomously evaluates and discards false-positive bridge candidates:

1. Discovers N bridge candidates via RRF hybrid search
2. Evaluates each candidate's mechanistic relevance (not just keyword overlap)
3. Discards surface-level matches: *"This connection is keyword-only — no mechanistic similarity. Discarded."*
4. Re-searches with alternative concepts to find replacement bridges
5. Records all discard/accept decisions in the Thought Log

### Parameter Auto-Tuning

The agent autonomously adjusts DETECT parameters based on SURVEY results:

- **High domain density** (>500 papers): lowers gap threshold to 0.10-0.20
- **Low domain density** (<50 papers): raises gap threshold to 0.15-0.30
- All adjustments are logged with reasoning in the Thought Log

### Thought Log

Real-time exposure of the agent's decision-making process:
- ES|QL queries executed and their results
- Index selection reasoning
- Self-Correction discard/accept judgments
- Parameter adjustment rationale

---

## Elasticsearch Features

Terra Incognita leverages **9 Elasticsearch capabilities**:

| ES Feature | Tool/Step | Role |
|-----------|-----------|------|
| `semantic_text` + ELSER v2 | SURVEY, BRIDGE | Semantic embedding + search for papers; drastically reduces dev time |
| RRF hybrid search | SURVEY, BRIDGE | BM25 + Vector fusion; "unexpected connections" (the technical implementation of serendipity) |
| ES\|QL | DETECT, VALIDATE | Cross-domain density analysis, paper counting, IVI calculation |
| ES\|QL + arXiv cross-list | VALIDATE | Multi-category papers = "existing bridge" labels; distinguish truly unexplored areas |
| Semantic Negative Search | DETECT | Density-based gap detection ("1,000 papers nearby, 0 at intersection A-B") |
| Agent Builder (`ai.agent`) | BRIDGE, PROPOSE | Multi-step reasoning, Self-Correction, parameter auto-tuning, hypothesis generation |
| Cloud Scheduler + MCP | Daily Discovery | Automated daily gap exploration + Discovery Card generation via Converse API |
| Cloud Scheduler + MCP | Gap Watch | Daily monitoring of open gaps for new papers — automated alerts |
| Index Alias | Time-Travel Discovery | Backtest alias separation (`papers_before_2020` vs `papers_all`) |

---

## Differentiation

| Feature | Semantic Scholar | Connected Papers | Elicit | **Terra Incognita** |
|---------|-----------------|-------------------|--------|---------------------|
| Paper search | Yes | Yes | Yes | Yes |
| Citation graph | Yes | Yes | No | No (unnecessary) |
| **Research gap detection** | No | No | No | **Yes (unique)** |
| **Cross-domain bridging** | No | No | No | **Yes (unique)** |
| **Novelty verification** | No | No | No | **Yes (unique)** |
| Research hypothesis generation | No | No | Partial | Yes |
| **Quantitative scoring (IVI/SP)** | No | No | No | **Yes (unique)** |
| **Agent self-correction** | No | No | No | Yes (Self-Correction) |
| **Gap monitoring** | No | No | No | Yes (Cloud Scheduler) |
| **Shareable Discovery Card** | No | No | No | Yes |

**Core message**: Existing tools search for papers that exist. Terra Incognita discovers research that doesn't exist yet.

---

## Discovery Card

The agent automatically generates a 1-page shareable Discovery Card for each finding:

| Element | Content |
|---------|---------|
| Hypothesis title | 1-line summary |
| Gap summary | + Innovation Vacuum Index (percentile) |
| Top 2 Bridges | + Serendipity Probability |
| Evidence papers (3) | Title + role tagging (Gap / Bridge / Context) |
| Confidence | HIGH / MEDIUM / LOW |

**Sample Discovery Card**:

```
+----------------------------------------------+
|  Zwitterionic Polymer x                      |
|  Alzheimer's Amyloid-Beta                    |
|                                              |
|  Innovation Vacuum: top 2%                   |
|  Serendipity: top 5%                         |
|  Cross-papers: 0 -- completely unexplored    |
|                                              |
|  Confidence: HIGH                            |
+----------------------------------------------+
```

---

## Components

### Indices (5)

| Index | Purpose |
|-------|---------|
| `ti-papers` | Paper corpus (17,000+ papers, 12 domains, `semantic_text` + ELSER) |
| `ti-gaps` | Detected research gaps with Innovation Vacuum Index |
| `ti-bridges` | Cross-domain bridges with Serendipity Probability |
| `ti-exploration-log` | Audit log of agent exploration sessions + Thought Log |
| `ti-discovery-cards` | Auto-generated shareable Discovery Cards |

### Tools (5 custom + 2 platform)

| Tool | Type | Function |
|------|------|----------|
| `ti-survey` | ES\|QL | STEP 1 — Per-domain relevance profiling via semantic search |
| `ti-detect` | ES\|QL | STEP 2 — Gap detection with density analysis + IVI |
| `ti-bridge` | ES\|QL | STEP 3 — Cross-domain bridge discovery via RRF |
| `ti-validate` | ES\|QL | STEP 4 — Novelty verification via cross-category count |
| `ti-save-results` | MCP | Result storage — writes to 4 indices via MCP server |
| `platform.core.execute_esql` | Built-in | Ad-hoc ES\|QL queries (backtest mode) |
| `platform.core.search` | Built-in | Index search for validation |

### MCP Server

Agent Builder's esql tools are **read-only** (ES|QL = SELECT only). The MCP server provides write capability and Cloud Scheduler automation:

```
Agent Builder → .mcp connector → Cloud Run (HTTPS) → MCP Server (FastMCP) → ES REST API
                                                                            → ti-gaps
                                                                            → ti-bridges
                                                                            → ti-discovery-cards
                                                                            → ti-exploration-log

Cloud Scheduler → OIDC auth → Cloud Run → MCP Server → Converse API / ES REST API
```

- **Stack**: FastMCP, Streamable HTTP transport, Python 3.12, httpx
- **Tools**:
  - `ti_save_results(result_type, data)` — Result storage, dispatching to 4 indices
  - `ti_daily_discovery()` — Automated exploration via Converse API (Cloud Scheduler)
  - `ti_gap_watch()` — Automated gap monitoring via ES direct query (Cloud Scheduler)
- **Deployment**: Cloud Run (`mcp-server/Dockerfile`)

### Agent (1)

**Terra Incognita Scout** — An autonomous research gap detection agent with a 5-step workflow (SURVEY > DETECT > BRIDGE > VALIDATE > PROPOSE), Self-Correction protocol, parameter auto-tuning, and Discovery Card generation.

---

## Setup Guide

### Prerequisites

- Elastic Cloud Hosted (ES 9.x) with ELSER v2 (`.elser-2-elastic`) deployed
- Agent Builder enabled
- `bash`, `curl`, `jq` available

### Step-by-Step

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env: ES_URL, ES_API_KEY, KIBANA_URL, MCP_SERVER_URL

# 2. Deploy MCP server (Docker → Cloud Run or any HTTPS endpoint)
docker build -t ti-mcp-server mcp-server/
# Deploy and set MCP_SERVER_URL in .env

# 3. Deploy in order (each script depends on the previous)
bash setup/01-indices.sh      # 5 ES indices
bash setup/02-aliases.sh      # Backtest aliases
bash setup/03-tools.sh        # 4 ES|QL tools
bash setup/08-mcp-save.sh     # MCP connector + save tool
bash setup/04-agent.sh        # 1 agent
bash setup/05-ingest.sh       # Paper data
bash setup/06-seed-data.sh    # Seed data
bash setup/07-dashboard.sh    # Dashboard import

# 4. (Optional) Cloud Scheduler setup — requires gcloud CLI
bash setup/09-scheduler.sh    # Daily Discovery + Gap Watch cron jobs
```

> Scripts 01-02, 05-06 target `ES_URL`. Scripts 03-04, 07 target `KIBANA_URL`. Script 09 uses `gcloud` CLI. Both use `ES_API_KEY` for auth. All seed data is **synthetic** — no real or confidential data is used.

---

## Project Structure

```
terra-incognita/
├── agent/           # Agent definition (9 rules)
├── dashboard/       # Kibana dashboard NDJSON
├── docs/            # Hackathon reference documentation
├── indices/         # Index mappings
├── ingest/          # Data pipeline (arXiv collector + NDJSON)
├── seed-data/       # Seed data NDJSON
├── mcp-server/      # MCP server for write + automation (FastMCP + Cloud Run)
├── setup/           # Setup scripts (01-09)
├── tools/           # ES|QL tool definitions
├── .env.example     # Environment template
├── CLAUDE.md        # AI assistant guide
└── README.md        # This file
```

---

## Technology Stack

| Technology | Usage |
|-----------|-------|
| **Elasticsearch 9.x** | Primary data store, semantic search (ELSER), index aliases for backtest |
| **ELSER v2** | Semantic search via `semantic_text` field type — zero-config embeddings |
| **ES\|QL** | Parameterized queries for gap detection, density analysis, novelty verification |
| **RRF Hybrid Search** | BM25 + Vector fusion for discovering "unexpected connections" |
| **MCP Server** | FastMCP + Cloud Run for write operations + Cloud Scheduler automation |
| **Cloud Scheduler** | Daily automated exploration (ti_daily_discovery) + gap monitoring (ti_gap_watch) |
| **Agent Builder** | Tool registration, agent management, multi-step reasoning |
| **Kibana 9.x** | Dashboard visualization, agent conversation UI |
| **arXiv API** | Paper data source (12 domains, 17,000+ papers) |

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

<p align="center">
  <b>Terra Incognita</b> — Discovering what science hasn't explored yet.
</p>
