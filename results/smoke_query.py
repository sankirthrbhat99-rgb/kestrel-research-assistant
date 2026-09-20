"""Phase 1 smoke script: show top-6 results for the KQL timeout query.

Usage::

    python results/smoke_query.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kestrel import config  # noqa: E402
from kestrel.retrieval import Retriever  # noqa: E402

QUERY = "What is the KQL query timeout?"


def main() -> int:
    retriever = Retriever()

    print(f"Corpus size: {retriever.size} chunks")
    print(f"Default strategy: {config.DEFAULT_STRATEGY}")
    print(f"Query: {QUERY!r}\n")

    for strategy in ("dense", "bm25", "hybrid"):
        results = retriever.search_corpus(QUERY, k=6, strategy=strategy)
        print("=" * 78)
        print(f"STRATEGY: {strategy}  (top {len(results)})")
        print("=" * 78)
        for rank, result in enumerate(results, start=1):
            print(f"{rank}. {result.chunk_id}")
            print(f"   title: {result.title}")
            print(f"   score: {result.score:.6f}   sources: {result.sources}")
            snippet = " ".join(result.text.split())[:170]
            print(f"   text : {snippet}...")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())