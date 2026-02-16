# Terra Incognita — Devpost Description

## The Problem

Every research discovery tool today — Semantic Scholar, Connected Papers, Elicit — answers the same question: *"What papers exist?"* But scientific breakthroughs don't come from known literature. Penicillin emerged from a gap between bacteriology and mycology. CRISPR was born at the intersection of gene editing and bacterial immunology. The most valuable territory in science is the **space between papers** — and no tool searches for it.

## The Solution

Terra Incognita is an autonomous research gap detection agent built on Elasticsearch Agent Builder. Instead of searching for existing papers, it maps the landscape of 6,000+ scientific papers across 6 domains, identifies "meaningful voids" where research *should* exist but doesn't, and proposes cross-disciplinary bridges to fill them.

The agent follows a 5-step workflow — SURVEY, DETECT, BRIDGE, VALIDATE, PROPOSE — each backed by a dedicated ES|QL tool. It produces two quantitative scores: **Innovation Vacuum Index** (how meaningfully empty a gap is, displayed as percentiles like "top 2%") and **Serendipity Probability** (how promising a cross-domain bridge is). Every finding is packaged as a shareable **Discovery Card**.

## Technical Implementation

Terra Incognita leverages **9 Elasticsearch capabilities**: `semantic_text` with ELSER v2 for zero-config semantic embeddings; **RRF hybrid search** fusing BM25 and vector scores to surface unexpected connections; **ES|QL** for cross-domain density analysis and novelty verification; **Agent Builder** orchestrating multi-step autonomous reasoning; **Index Aliases** enabling Time-Travel backtesting (pre-2020 data for discovery, full corpus for validation); and **Cloud Scheduler** powering Gap Watch alerts and Daily Discovery workflows. Write operations flow through a custom **MCP server** (FastMCP on Cloud Run), since ES|QL tools are read-only.

## What Makes It Different

The agent exhibits genuine autonomy. A **Self-Correction Protocol** during the BRIDGE step rejects keyword-only matches ("nano + neural" overlap without mechanistic relevance) and re-searches with refined concepts. **Parameter Auto-Tuning** dynamically adjusts gap thresholds based on domain density. All decisions are recorded in a transparent Thought Log.

## Demo Highlight

Query: *"Find unexplored research directions in Alzheimer's treatment."* The agent surveys 6 domains, detects a meaningful gap in materials science (IVI: top 2%), rejects a false bridge candidate, then discovers that **zwitterionic anti-fouling polymers** share the same protein-adhesion-prevention mechanism as amyloid-beta aggregation inhibition — with **zero** existing cross-papers. A completely unexplored intersection between two mature fields, found autonomously.
