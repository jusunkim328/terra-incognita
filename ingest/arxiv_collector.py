#!/usr/bin/env python3
"""
Terra Incognita arXiv Collector
Collects papers (12 domains × 1,000) and bulk indexes to Elasticsearch.

Usage:
  python3 arxiv_collector.py                    # Recent papers (default)
  python3 arxiv_collector.py --before 2020      # Papers before 2020 (backtest)
"""

import argparse
import arxiv
import json
import os
import sys
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

ES_URL = os.getenv("ES_URL")
ES_API_KEY = os.getenv("ES_API_KEY")

if not ES_URL or not ES_API_KEY:
    print("ERROR: ES_URL and ES_API_KEY must be set in .env")
    sys.exit(1)

DOMAINS = {
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

MAX_PER_DOMAIN = 1000
BULK_CHUNK_SIZE = 500
RATE_LIMIT_SECONDS = 3


def extract_arxiv_id(entry_id: str) -> str:
    """Extract clean arXiv ID from entry URL."""
    # http://arxiv.org/abs/2401.12345v1 -> 2401.12345
    return entry_id.split("/abs/")[-1].split("v")[0] if "/abs/" in entry_id else entry_id


def collect_domain(
    domain_name: str,
    query: str,
    before_year: int | None = None,
    max_results: int = MAX_PER_DOMAIN,
    seen_ids: set[str] | None = None,
) -> list[dict]:
    """Collect papers for a single domain from arXiv.

    Args:
        seen_ids: Set of arxiv_ids already collected in other domains.
                  Cross-listed papers are skipped to preserve domain accuracy.
    """
    full_query = query
    if before_year:
        # arXiv date filter: submittedDate:[YYYYMMDDTTTT TO YYYYMMDDTTTT]
        full_query = f"{query} AND submittedDate:[200001010000 TO {before_year - 1}12312359]"

    print(f"\n{'='*60}")
    print(f"Collecting: {domain_name}")
    print(f"  Query: {full_query}")
    print(f"{'='*60}")

    client = arxiv.Client(
        page_size=100,
        delay_seconds=RATE_LIMIT_SECONDS,
        num_retries=5,
    )
    search = arxiv.Search(
        query=full_query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    papers = []
    skipped = 0
    backoff = 5

    for i, result in enumerate(client.results(search)):
        try:
            arxiv_id = extract_arxiv_id(result.entry_id)

            if seen_ids is not None and arxiv_id in seen_ids:
                skipped += 1
                continue
            if seen_ids is not None:
                seen_ids.add(arxiv_id)

            doc = {
                "arxiv_id": arxiv_id,
                "title": result.title,
                "abstract": result.summary,
                "content": f"{result.title}. {result.summary}",
                "primary_category": result.primary_category,
                "categories": result.categories,
                "domain": domain_name,
                "published": result.published.isoformat(),
                "authors": [a.name for a in result.authors[:10]],
            }
            papers.append(doc)

            if (i + 1) % 100 == 0:
                print(f"  Collected {len(papers)}/{max_results} papers"
                      f"{f' (skipped {skipped} cross-listed)' if skipped else ''}")
                backoff = 5  # Reset backoff on success

        except Exception as e:
            print(f"  Error on paper {i}: {e}")
            time.sleep(backoff)
            backoff = min(backoff * 2, 120)

    print(f"  Total collected: {len(papers)} papers"
          f"{f', skipped {skipped} cross-listed' if skipped else ''}")
    return papers, skipped


def bulk_index(papers: list[dict], index_name: str = "ti-papers") -> dict:
    """Bulk index papers to Elasticsearch."""
    if not papers:
        return {"indexed": 0, "errors": 0}

    total_indexed = 0
    total_errors = 0

    for chunk_start in range(0, len(papers), BULK_CHUNK_SIZE):
        chunk = papers[chunk_start:chunk_start + BULK_CHUNK_SIZE]

        # Build NDJSON
        lines = []
        for doc in chunk:
            action = {"index": {"_index": index_name, "_id": doc["arxiv_id"]}}
            lines.append(json.dumps(action))
            lines.append(json.dumps(doc, ensure_ascii=False))
        body = "\n".join(lines) + "\n"

        # Send bulk request
        backoff = 5
        for attempt in range(5):
            try:
                resp = requests.post(
                    f"{ES_URL}/_bulk",
                    headers={
                        "Content-Type": "application/x-ndjson",
                        "Authorization": f"ApiKey {ES_API_KEY}",
                    },
                    data=body.encode("utf-8"),
                    timeout=120,
                )

                if resp.status_code == 200:
                    result = resp.json()
                    errors = sum(1 for item in result.get("items", [])
                               if item.get("index", {}).get("error"))
                    indexed = len(chunk) - errors
                    total_indexed += indexed
                    total_errors += errors
                    print(f"  Bulk indexed {chunk_start + len(chunk)}/{len(papers)} "
                          f"(chunk: {indexed} ok, {errors} errors)")
                    break
                else:
                    print(f"  Bulk request failed ({resp.status_code}), attempt {attempt + 1}/5")
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 120)

            except Exception as e:
                print(f"  Bulk request error: {e}, attempt {attempt + 1}/5")
                time.sleep(backoff)
                backoff = min(backoff * 2, 120)
        else:
            print(f"  GAVE UP on chunk {chunk_start}-{chunk_start + len(chunk)}"
                  f" after 5 attempts", file=sys.stderr)
            total_errors += len(chunk)

    return {"indexed": total_indexed, "errors": total_errors}


def main():
    parser = argparse.ArgumentParser(description="Terra Incognita arXiv Collector")
    parser.add_argument("--before", type=int, default=None,
                        help="Collect papers before this year (e.g. --before 2020)")
    parser.add_argument("--max-per-domain", type=int, default=MAX_PER_DOMAIN,
                        help=f"Max papers per domain (default: {MAX_PER_DOMAIN})")
    parser.add_argument("--index-name", type=str, default="ti-papers",
                        help="Target Elasticsearch index name (default: ti-papers)")
    args = parser.parse_args()

    label = f"before {args.before}" if args.before else "recent"
    print("=" * 60)
    print(f"Terra Incognita — arXiv Collector ({label})")
    print(f"ES_URL: {ES_URL}")
    print(f"Domains: {len(DOMAINS)}, Papers per domain: {args.max_per_domain}")
    print(f"Index:   {args.index_name}")
    print("=" * 60)

    ndjson_name = f"papers_before_{args.before}.ndjson" if args.before else "papers.ndjson"
    ndjson_path = Path(__file__).parent / ndjson_name

    if ndjson_path.exists():
        print(f"WARNING: {ndjson_path} already exists, overwriting")
    ndjson_path.write_text("")  # Truncate before starting

    total_stats = {"collected": 0, "indexed": 0, "errors": 0, "skipped": 0}
    seen_ids: set[str] = set()

    for domain_name, query in DOMAINS.items():
        papers, skipped = collect_domain(
            domain_name, query,
            before_year=args.before,
            max_results=args.max_per_domain,
            seen_ids=seen_ids,
        )
        total_stats["collected"] += len(papers)
        total_stats["skipped"] += skipped

        # Save to NDJSON file (append per domain, file truncated at start)
        with open(ndjson_path, "a", encoding="utf-8") as f:
            for doc in papers:
                f.write(json.dumps({"index": {"_index": args.index_name, "_id": doc["arxiv_id"]}}) + "\n")
                f.write(json.dumps(doc, ensure_ascii=False) + "\n")

        # Bulk index to ES
        result = bulk_index(papers, index_name=args.index_name)
        total_stats["indexed"] += result["indexed"]
        total_stats["errors"] += result["errors"]

        # Rate limit between domains
        print(f"\n  Waiting {RATE_LIMIT_SECONDS}s before next domain...")
        time.sleep(RATE_LIMIT_SECONDS)

    print("\n" + "=" * 60)
    print("Collection Complete")
    print("=" * 60)
    print(f"Total collected: {total_stats['collected']}")
    print(f"Total indexed:   {total_stats['indexed']}")
    print(f"Total errors:    {total_stats['errors']}")
    if total_stats["skipped"]:
        print(f"Cross-listed skipped: {total_stats['skipped']}")
    print(f"NDJSON saved:    {ndjson_path}")


if __name__ == "__main__":
    main()
