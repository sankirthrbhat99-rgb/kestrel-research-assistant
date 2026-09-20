"""Retrieval over the ingested Kestrel corpus.

Strategies
----------
* ``dense``  -- cosine similarity against bge-small-en-v1.5 embeddings in Chroma.
* ``bm25``   -- lexical BM25 (rank_bm25) over the raw chunk text.
* ``hybrid`` -- BM25 + dense fused with Reciprocal Rank Fusion (RRF).

``dense`` is the Phase 1 baseline. Neighbour expansion (pulling in adjacent
chunks from the same document) is supported but disabled by default, and final
results are always deduplicated by chunk id.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from . import config
from .ingest import Embedder, get_chroma_collection, load_bm25_payload, tokenize


@dataclass
class SearchResult:
    """A single retrieved chunk with provenance and scoring detail."""

    chunk_id: str
    text: str
    score: float
    title: str = ""
    doc_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    # Which retriever(s) produced this hit and at what rank/score.
    sources: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "title": self.title,
            "doc_id": self.doc_id,
            "score": self.score,
            "sources": self.sources,
            "metadata": self.metadata,
        }


def dedupe(results: Iterable[SearchResult]) -> list[SearchResult]:
    """Collapse duplicate chunk ids, keeping the highest-scoring occurrence.

    Order is preserved by best score so the caller still sees a ranking.
    """
    best: dict[str, SearchResult] = {}
    for result in results:
        current = best.get(result.chunk_id)
        if current is None or result.score > current.score:
            if current is not None:
                # Merge provenance so a hybrid hit records both retrievers.
                merged = dict(current.sources)
                merged.update(result.sources)
                result.sources = merged
            best[result.chunk_id] = result
        else:
            current.sources.update(result.sources)
    return sorted(best.values(), key=lambda r: r.score, reverse=True)


def rrf_fuse(
    ranked_lists: dict[str, list[str]], *, rrf_k: int = config.RRF_K
) -> dict[str, float]:
    """Reciprocal Rank Fusion over several ranked id lists.

    score(d) = sum over retrievers of 1 / (rrf_k + rank(d)), rank starting at 1.
    """
    scores: dict[str, float] = {}
    for ids in ranked_lists.values():
        for rank, chunk_id in enumerate(ids, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)
    return scores


class Retriever:
    """Loads the persisted indexes and answers corpus queries."""

    def __init__(self, embedder: Embedder | None = None) -> None:
        self._payload: dict[str, Any] | None = None
        self._collection: Any | None = None
        self._embedder = embedder
        # chunk_id -> metadata, for neighbour expansion.
        self._by_ordinal: dict[int, dict[str, Any]] | None = None

    # -- lazy resources ----------------------------------------------------

    @property
    def payload(self) -> dict[str, Any]:
        if self._payload is None:
            self._payload = load_bm25_payload()
        return self._payload

    @property
    def collection(self) -> Any:
        if self._collection is None:
            self._collection = get_chroma_collection()
        return self._collection

    @property
    def embedder(self) -> Embedder:
        if self._embedder is None:
            self._embedder = Embedder()
        return self._embedder

    @property
    def size(self) -> int:
        return len(self.payload["chunk_ids"])

    def _ordinal_map(self) -> dict[int, dict[str, Any]]:
        """Map ordinal -> {chunk_id, text, title, metadata} for expansion."""
        if self._by_ordinal is None:
            ids = self.payload["chunk_ids"]
            texts = self.payload["texts"]
            titles = self.payload["titles"]
            metas = self.payload["metadatas"]
            self._by_ordinal = {
                i: {
                    "chunk_id": ids[i],
                    "text": texts[i],
                    "title": titles[i],
                    "metadata": metas[i],
                }
                for i in range(len(ids))
            }
        return self._by_ordinal

    def _meta_for(self, chunk_id: str) -> dict[str, Any]:
        ids = self.payload["chunk_ids"]
        try:
            return self.payload["metadatas"][ids.index(chunk_id)]
        except ValueError:
            return {}

    # -- individual retrievers --------------------------------------------

    def dense_search(self, query: str, k: int) -> list[SearchResult]:
        """Vector search over Chroma using the bge query embedding."""
        vector = self.embedder.encode_query(query)
        response = self.collection.query(
            query_embeddings=[vector],
            n_results=min(k, self.collection.count() or k),
            include=["documents", "metadatas", "distances"],
        )
        ids = (response.get("ids") or [[]])[0]
        docs = (response.get("documents") or [[]])[0]
        metas = (response.get("metadatas") or [[]])[0]
        distances = (response.get("distances") or [[]])[0]

        results: list[SearchResult] = []
        for i, chunk_id in enumerate(ids):
            meta = dict(metas[i] or {}) if i < len(metas) else {}
            distance = float(distances[i]) if i < len(distances) else 0.0
            # Chroma cosine distance is 1 - cosine_similarity; convert back so
            # higher is always better, matching BM25 and RRF.
            similarity = 1.0 - distance
            results.append(
                SearchResult(
                    chunk_id=chunk_id,
                    text=docs[i] if i < len(docs) else "",
                    score=similarity,
                    title=str(meta.get("title", "")),
                    doc_id=str(meta.get("doc_id", "")),
                    metadata=meta,
                    sources={"dense_rank": i + 1, "dense_score": similarity},
                )
            )
        return results

    def bm25_search(self, query: str, k: int) -> list[SearchResult]:
        """Lexical BM25 search over the tokenized corpus."""
        payload = self.payload
        bm25 = payload["bm25"]
        tokens = tokenize(query)
        if not tokens:
            return []
        scores = bm25.get_scores(tokens)
        # Stable sort by descending score.
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        ids = payload["chunk_ids"]
        texts = payload["texts"]
        titles = payload["titles"]
        metas = payload["metadatas"]

        results: list[SearchResult] = []
        for rank, idx in enumerate(order, start=1):
            results.append(
                SearchResult(
                    chunk_id=ids[idx],
                    text=texts[idx],
                    score=float(scores[idx]),
                    title=titles[idx],
                    doc_id=str(metas[idx].get("doc_id", "")),
                    metadata=dict(metas[idx]),
                    sources={"bm25_rank": rank, "bm25_score": float(scores[idx])},
                )
            )
        return results

    # -- fusion ------------------------------------------------------------

    def hybrid_search(
        self, query: str, k: int, *, candidates: int, rrf_k: int = config.RRF_K
    ) -> list[SearchResult]:
        """BM25 + dense fused with RRF."""
        dense = self.dense_search(query, candidates)
        sparse = self.bm25_search(query, candidates)

        fused = rrf_fuse(
            {
                "dense": [r.chunk_id for r in dense],
                "bm25": [r.chunk_id for r in sparse],
            },
            rrf_k=rrf_k,
        )

        pool: dict[str, SearchResult] = {r.chunk_id: r for r in sparse}
        pool.update({r.chunk_id: r for r in dense})

        # Rank in each retriever for provenance reporting.
        dense_rank = {r.chunk_id: i for i, r in enumerate(dense, start=1)}
        bm25_rank = {r.chunk_id: i for i, r in enumerate(sparse, start=1)}

        results: list[SearchResult] = []
        for chunk_id, score in fused.items():
            base = pool[chunk_id]
            sources: dict[str, Any] = {"rrf_score": score}
            if chunk_id in dense_rank:
                sources["dense_rank"] = dense_rank[chunk_id]
            if chunk_id in bm25_rank:
                sources["bm25_rank"] = bm25_rank[chunk_id]
            results.append(
                SearchResult(
                    chunk_id=base.chunk_id,
                    text=base.text,
                    score=score,
                    title=base.title,
                    doc_id=base.doc_id,
                    metadata=base.metadata,
                    sources=sources,
                )
            )

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:k]

    # -- neighbour expansion ----------------------------------------------

    def expand_neighbors(
        self, results: list[SearchResult], *, window: int = 1
    ) -> list[SearchResult]:
        """Add adjacent chunks from the same document.

        Adjacency is by ``chunk_index`` within a ``doc_id``. Added neighbours
        score slightly below their seed so they never outrank direct hits.
        """
        by_doc: dict[str, dict[int, int]] = {}
        for ordinal, row in self._ordinal_map().items():
            meta = row["metadata"]
            doc_id = str(meta.get("doc_id", ""))
            chunk_index = int(meta.get("chunk_index", 0))
            by_doc.setdefault(doc_id, {})[chunk_index] = ordinal

        seen = {r.chunk_id for r in results}
        additions: list[SearchResult] = []
        for result in results:
            doc_id = result.doc_id or str(result.metadata.get("doc_id", ""))
            chunk_index = int(result.metadata.get("chunk_index", 0))
            index_map = by_doc.get(doc_id, {})
            for offset in range(-window, window + 1):
                if offset == 0:
                    continue
                neighbor_ordinal = index_map.get(chunk_index + offset)
                if neighbor_ordinal is None:
                    continue
                row = self._ordinal_map()[neighbor_ordinal]
                if row["chunk_id"] in seen:
                    continue
                seen.add(row["chunk_id"])
                additions.append(
                    SearchResult(
                        chunk_id=row["chunk_id"],
                        text=row["text"],
                        # Just below the seed, decaying with distance.
                        score=result.score * (0.999 - 0.001 * abs(offset)),
                        title=row["title"],
                        doc_id=doc_id,
                        metadata=dict(row["metadata"]),
                        sources={"neighbor_of": result.chunk_id, "offset": offset},
                    )
                )
        return results + additions

    # -- public API --------------------------------------------------------

    def search_corpus(
        self,
        query: str,
        k: int = config.DEFAULT_K,
        *,
        strategy: str | None = None,
        expand_neighbors: bool | None = None,
        settings: config.RetrievalSettings | None = None,
    ) -> list[SearchResult]:
        """Search the corpus and return the top ``k`` deduplicated results.

        ``strategy`` overrides the configured default ("dense", "bm25" or
        "hybrid"). ``expand_neighbors`` overrides the configured default
        (False). Returns at most ``k`` results after dedupe.
        """
        resolved = settings or config.RetrievalSettings(
            strategy=(strategy or config.DEFAULT_STRATEGY).lower(),
            k=k,
            expand_neighbors=(
                config.NEIGHBOR_EXPANSION_DEFAULT
                if expand_neighbors is None
                else expand_neighbors
            ),
        )
        if strategy and strategy.lower() != resolved.strategy:
            resolved = config.RetrievalSettings(
                strategy=strategy.lower(),
                k=k,
                candidates=resolved.candidates,
                rrf_k=resolved.rrf_k,
                expand_neighbors=resolved.expand_neighbors,
                neighbor_window=resolved.neighbor_window,
            )

        if not query or not query.strip():
            return []

        candidates = max(resolved.candidates, resolved.k)
        if resolved.strategy == "dense":
            results = self.dense_search(query, candidates)
        elif resolved.strategy == "bm25":
            results = self.bm25_search(query, candidates)
        elif resolved.strategy == "hybrid":
            results = self.hybrid_search(
                query, candidates, candidates=candidates, rrf_k=resolved.rrf_k
            )
        else:  # pragma: no cover - RetrievalSettings validates this
            raise ValueError(f"Unknown strategy: {resolved.strategy!r}")

        results = dedupe(results)

        if resolved.expand_neighbors:
            results = dedupe(
                self.expand_neighbors(results, window=resolved.neighbor_window)
            )

        return results[: resolved.k]


_DEFAULT_RETRIEVER: Retriever | None = None


def get_retriever() -> Retriever:
    """Return a process-wide default Retriever (indexes load lazily)."""
    global _DEFAULT_RETRIEVER
    if _DEFAULT_RETRIEVER is None:
        _DEFAULT_RETRIEVER = Retriever()
    return _DEFAULT_RETRIEVER


def search_corpus(
    query: str,
    k: int = config.DEFAULT_K,
    *,
    strategy: str | None = None,
    expand_neighbors: bool | None = None,
) -> list[SearchResult]:
    """Module-level convenience wrapper around ``Retriever.search_corpus``."""
    return get_retriever().search_corpus(
        query, k=k, strategy=strategy, expand_neighbors=expand_neighbors
    )


__all__ = [
    "Retriever",
    "SearchResult",
    "dedupe",
    "rrf_fuse",
    "get_retriever",
    "search_corpus",
]