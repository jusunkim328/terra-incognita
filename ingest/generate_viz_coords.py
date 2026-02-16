#!/usr/bin/env python3
"""Terra Incognita — 벡터 공간 시각화 좌표 생성

논문 코퍼스의 2D 시각화 좌표를 생성하여 ES에 업데이트합니다.
TF-IDF → t-SNE로 차원 축소 후 viz_x, viz_y 필드에 저장합니다.

Usage:
    pip install -r requirements-viz.txt
    python generate_viz_coords.py
"""

import json
import os
import sys
from pathlib import Path

import numpy as np
import requests
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.manifold import TSNE

# Load .env
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

ES_URL = os.getenv("ES_URL")
ES_API_KEY = os.getenv("ES_API_KEY")

if not ES_URL or not ES_API_KEY:
    print("ERROR: ES_URL and ES_API_KEY must be set in .env")
    sys.exit(1)

ES_HEADERS = {
    "Authorization": f"ApiKey {ES_API_KEY}",
    "Content-Type": "application/json",
}

SCROLL_SIZE = 1000
SCROLL_TIMEOUT = "5m"
INDEX = "ti-papers"

# t-SNE 파라미터
TSNE_PERPLEXITY = 30
TSNE_RANDOM_STATE = 42
TSNE_MAX_ITER = 1000

# Bulk update 청크 크기
BULK_CHUNK_SIZE = 500


def fetch_all_papers() -> list[dict]:
    """ES scroll API로 전체 논문을 가져옵니다."""
    papers = []

    # Initial search with scroll
    resp = requests.post(
        f"{ES_URL}/{INDEX}/_search?scroll={SCROLL_TIMEOUT}",
        headers=ES_HEADERS,
        json={
            "size": SCROLL_SIZE,
            "_source": ["arxiv_id", "content", "domain", "title"],
            "query": {"match_all": {}},
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()

    scroll_id = data.get("_scroll_id")
    hits = data.get("hits", {}).get("hits", [])
    papers.extend(hits)
    print(f"  Fetched {len(papers)} papers...")

    # Continue scrolling
    while hits:
        resp = requests.post(
            f"{ES_URL}/_search/scroll",
            headers=ES_HEADERS,
            json={"scroll": SCROLL_TIMEOUT, "scroll_id": scroll_id},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        scroll_id = data.get("_scroll_id")
        hits = data.get("hits", {}).get("hits", [])
        papers.extend(hits)
        if hits:
            print(f"  Fetched {len(papers)} papers...")

    # Clear scroll
    try:
        requests.delete(
            f"{ES_URL}/_search/scroll",
            headers=ES_HEADERS,
            json={"scroll_id": scroll_id},
            timeout=10,
        )
    except Exception:
        pass

    return papers


def compute_2d_coords(papers: list[dict]) -> np.ndarray:
    """TF-IDF + t-SNE로 2D 좌표를 계산합니다."""
    # Extract content for TF-IDF
    contents = []
    for p in papers:
        src = p.get("_source", {})
        text = src.get("content", "") or f"{src.get('title', '')}. {src.get('abstract', '')}"
        contents.append(text)

    print(f"  Vectorizing {len(contents)} documents with TF-IDF...")
    vectorizer = TfidfVectorizer(
        max_features=5000,
        stop_words="english",
        min_df=2,
        max_df=0.95,
    )
    tfidf_matrix = vectorizer.fit_transform(contents)
    print(f"  TF-IDF matrix shape: {tfidf_matrix.shape}")

    # Adjust perplexity if fewer samples
    perplexity = min(TSNE_PERPLEXITY, len(papers) - 1)
    if perplexity < 5:
        perplexity = 5

    print(f"  Running t-SNE (perplexity={perplexity}, n_iter={TSNE_MAX_ITER})...")
    tsne = TSNE(
        n_components=2,
        perplexity=perplexity,
        random_state=TSNE_RANDOM_STATE,
        max_iter=TSNE_MAX_ITER,
        learning_rate="auto",
        init="pca",
    )
    coords_2d = tsne.fit_transform(tfidf_matrix.toarray())
    print(f"  t-SNE complete. Shape: {coords_2d.shape}")

    return coords_2d


def normalize_coords(coords: np.ndarray) -> np.ndarray:
    """좌표를 0~100 범위로 정규화합니다."""
    for dim in range(coords.shape[1]):
        col = coords[:, dim]
        min_val, max_val = col.min(), col.max()
        if max_val - min_val > 0:
            coords[:, dim] = (col - min_val) / (max_val - min_val) * 100
        else:
            coords[:, dim] = 50.0
    return coords


def bulk_update_coords(papers: list[dict], coords: np.ndarray) -> dict:
    """ES _bulk API로 viz_x, viz_y 좌표를 업데이트합니다."""
    total_updated = 0
    total_errors = 0

    for chunk_start in range(0, len(papers), BULK_CHUNK_SIZE):
        chunk_end = min(chunk_start + BULK_CHUNK_SIZE, len(papers))
        lines = []

        for i in range(chunk_start, chunk_end):
            doc_id = papers[i]["_id"]
            viz_x = round(float(coords[i, 0]), 2)
            viz_y = round(float(coords[i, 1]), 2)
            lines.append(json.dumps({"update": {"_index": INDEX, "_id": doc_id}}))
            lines.append(json.dumps({"doc": {"viz_x": viz_x, "viz_y": viz_y}}))

        body = "\n".join(lines) + "\n"

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
                    errors = sum(
                        1
                        for item in result.get("items", [])
                        if item.get("update", {}).get("error")
                    )
                    updated = (chunk_end - chunk_start) - errors
                    total_updated += updated
                    total_errors += errors
                    print(
                        f"  Updated {chunk_end}/{len(papers)} "
                        f"(chunk: {updated} ok, {errors} errors)"
                    )
                    break
                else:
                    print(f"  Bulk update failed ({resp.status_code}), attempt {attempt + 1}/5")
                    import time
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 120)
            except Exception as e:
                print(f"  Bulk update error: {e}, attempt {attempt + 1}/5")
                import time
                time.sleep(backoff)
                backoff = min(backoff * 2, 120)
        else:
            print(f"  GAVE UP on chunk {chunk_start}-{chunk_end}")
            total_errors += chunk_end - chunk_start

    return {"updated": total_updated, "errors": total_errors}


def main():
    print("=" * 60)
    print("Terra Incognita — Vector Space Visualization")
    print(f"ES_URL: {ES_URL}")
    print("=" * 60)

    # Step 1: Fetch all papers
    print("\n[Step 1] Fetching papers from ES...")
    papers = fetch_all_papers()
    print(f"  Total papers: {len(papers)}")

    if len(papers) < 10:
        print("ERROR: Not enough papers for t-SNE (need at least 10)")
        sys.exit(1)

    # Step 2: Compute 2D coordinates
    print("\n[Step 2] Computing 2D coordinates...")
    coords = compute_2d_coords(papers)

    # Step 3: Normalize to 0-100 range
    print("\n[Step 3] Normalizing coordinates to 0-100 range...")
    coords = normalize_coords(coords)

    # Step 4: Update ES with coordinates
    print("\n[Step 4] Updating ES with viz coordinates...")
    result = bulk_update_coords(papers, coords)

    print("\n" + "=" * 60)
    print("Visualization Complete")
    print("=" * 60)
    print(f"  Papers processed: {len(papers)}")
    print(f"  Updated: {result['updated']}")
    print(f"  Errors: {result['errors']}")

    # Print domain distribution
    domain_counts: dict[str, int] = {}
    for p in papers:
        domain = p.get("_source", {}).get("domain", "unknown")
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
    print("\n  Domain distribution:")
    for domain, count in sorted(domain_counts.items()):
        print(f"    {domain}: {count}")


if __name__ == "__main__":
    main()
