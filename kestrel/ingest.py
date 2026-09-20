"""Corpus ingestion: read corpus.jsonl, embed locally, persist Chroma + BM25.

Design notes
------------
* The corpus is opened read-only and is never rewritten, reformatted, or
  truncated. Ingestion only ever *reads* it.
* Embeddings are produced locally with BAAI/bge-small-en-v1.5 via
  sentence-transformers. No network calls happen at query time.
* Chroma is used in persistent mode so the vector store survives process exit.
* BM25 is built with rank_bm25 and pickled next to the Chroma store.
* A manifest records the corpus SHA-256, the embedding model, and the chunk
  ids. If the hash and model are unchanged, ingestion is skipped and the
  existing index is reused.

Run as a module::

    python -m kestrel.ingest              # build, or reuse if unchanged
    python -m kestrel.ingest --rebuild    # force a full rebuild
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from . import config

# --------------------------------------------------------------------------
# Corpus reading (read-only)
# --------------------------------------------------------------------------

REQUIRED_FIELDS = ("chunk_id", "doc_id", "title", "text")


class CorpusError(RuntimeError):
    """Raised when corpus.jsonl is missing or structurally invalid."""


@dataclass(frozen=True)
class Chunk:
    """A single corpus chunk plus derived ordering metadata."""

    chunk_id: str
    doc_id: str
    title: str
    text: str
    metadata: dict[str, Any]
    chunk_index: int
    ordinal: int

    def to_metadata(self) -> dict[str, Any]:
        """Metadata dict persisted to Chroma and the BM25 sidecar."""
        meta = dict(self.metadata)
        meta["chunk_id"] = self.chunk_id
        meta["chunk_index"] = self.chunk_index
        meta["ordinal"] = self.ordinal
        return meta


def sha256_of_file(path: Path, *, chunk_size: int = 1 << 20) -> str:
    """Return the hex SHA-256 of ``path``, streaming so large files are fine."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:  # read-only; never opened for writing
        while block := handle.read(chunk_size):
            digest.update(block)
    return digest.hexdigest()


def _chunk_index_from_id(chunk_id: str) -> int:
    """Extract the numeric suffix of ``doc:index`` style ids (0 if absent)."""
    match = re.search(r":(\d+)$", chunk_id)
    return int(match.group(1)) if match else 0


def load_corpus(path: Path | None = None) -> list[Chunk]:
    """Load and validate corpus.jsonl.

    Raises ``CorpusError`` for a missing file, malformed JSON, or a missing
    required field. Blank lines are skipped.
    """
    corpus_path = Path(path or config.CORPUS_PATH)
    if not corpus_path.exists():
        raise CorpusError(
            f"corpus.jsonl not found at {corpus_path}. "
            "Place the corpus at the repo root or set KESTREL_CORPUS_PATH."
        )

    chunks: list[Chunk] = []
    with corpus_path.open("r", encoding="utf-8") as handle:
        for lineno, raw in enumerate(handle, start=1):
            if not raw.strip():
                continue
            try:
                record = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise CorpusError(f"Invalid JSON on line {lineno}: {exc}") from exc

            missing = [f for f in REQUIRED_FIELDS if not record.get(f)]
            if missing:
                raise CorpusError(f"Line {lineno} missing fields: {missing}")

            chunk_id = str(record["chunk_id"])
            metadata = {
                key: record.get(key)
                for key in config.METADATA.carried
                if key in record
            }
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    doc_id=str(record["doc_id"]),
                    title=str(record.get("title", "")),
                    text=str(record["text"]),
                    metadata=metadata,
                    chunk_index=_chunk_index_from_id(chunk_id),
                    ordinal=len(chunks),
                )
            )

    if not chunks:
        raise CorpusError(f"corpus.jsonl at {corpus_path} contained no records.")
    return chunks


def verify_corpus_hash(path: Path | None = None) -> tuple[str, bool]:
    """Return ``(actual_sha256, matches_expected)`` and warn on mismatch."""
    corpus_path = Path(path or config.CORPUS_PATH)
    actual = sha256_of_file(corpus_path)
    expected = config.EXPECTED_CORPUS_SHA256
    matches = actual == expected.lower()
    if not matches:
        print(
            f"WARNING: corpus SHA-256 mismatch.\n"
            f"  expected: {expected}\n"
            f"  actual:   {actual}\n"
            "  The corpus differs from the version this index was validated "
            "against. Continuing, because the corpus is read-only here and a "
            "legitimate update is possible. Set KESTREL_CORPUS_SHA256 to "
            "silence this warning.",
            file=sys.stderr,
        )
    return actual, matches


# --------------------------------------------------------------------------
# Embeddings
# --------------------------------------------------------------------------


class Embedder:
    """Lazy wrapper around a sentence-transformers model.

    The model is loaded on first use so that importing this module (and running
    tests that only need BM25) never pays the model-load cost.
    """

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or config.EMBEDDING_MODEL_NAME
        self._model: Any | None = None

    @property
    def model(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            config.MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            self._model = SentenceTransformer(
                self.model_name, cache_folder=str(config.MODEL_CACHE_DIR)
            )
        return self._model

    @property
    def dimension(self) -> int:
        return int(self.model.get_sentence_embedding_dimension())

    def encode_documents(
        self, texts: Iterable[str], *, batch_size: int = 32, show_progress: bool = False
    ) -> list[list[float]]:
        """Embed documents. No instruction prefix: bge uses it on queries only."""
        vectors = self.model.encode(
            list(texts),
            batch_size=batch_size,
            show_progress_bar=show_progress,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return [vector.tolist() for vector in vectors]

    def encode_query(self, query: str) -> list[float]:
        """Embed a query with the bge instruction prefix."""
        prefixed = f"{config.QUERY_INSTRUCTION}{query}"
        vector = self.model.encode(
            [prefixed],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )[0]
        return vector.tolist()


# --------------------------------------------------------------------------
# BM25
# --------------------------------------------------------------------------

TOKEN_RE = re.compile(r"[a-z0-9_]+")


def tokenize(text: str) -> list[str]:
    """Lowercase word/number tokenizer used for BM25 indexing and queries."""
    return TOKEN_RE.findall(text.lower())


def build_bm25(chunks: list[Chunk]) -> Any:
    """Build a BM25Okapi index over chunk texts."""
    from rank_bm25 import BM25Okapi

    tokenized = [tokenize(chunk.text) for chunk in chunks]
    return BM25Okapi(tokenized)


# --------------------------------------------------------------------------
# Chroma
# --------------------------------------------------------------------------


def get_chroma_collection(client: Any = None) -> Any:
    """Return (creating if needed) the persistent Chroma collection."""
    import chromadb

    config.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    if client is None:
        client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    return client.get_or_create_collection(
        name=config.COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


# --------------------------------------------------------------------------
# Ingestion driver
# --------------------------------------------------------------------------


@dataclass
class IngestReport:
    """Outcome of an ingestion run."""

    chunks: int
    corpus_sha256: str
    hash_matches: bool
    embedding_model: str
    reused: bool
    elapsed_s: float
    paths: dict[str, str]


def read_manifest() -> dict[str, Any] | None:
    """Return the stored manifest, or None if absent/unreadable."""
    if not config.MANIFEST_PATH.exists():
        return None
    try:
        return json.loads(config.MANIFEST_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def index_is_current(corpus_sha256: str, model_name: str) -> bool:
    """True when a reusable index matching this corpus + model already exists."""
    manifest = read_manifest()
    if not manifest:
        return False
    if manifest.get("corpus_sha256") != corpus_sha256:
        return False
    if manifest.get("embedding_model") != model_name:
        return False
    if not (config.BM25_PATH.exists() and config.CHROMA_DIR.exists()):
        return False
    # Guard against a partially written Chroma directory.
    try:
        collection = get_chroma_collection()
        return collection.count() == int(manifest.get("chunk_count", -1))
    except Exception:
        return False


def _persist_bm25(chunks: list[Chunk], bm25: Any) -> None:
    payload = {
        "chunk_ids": [chunk.chunk_id for chunk in chunks],
        "metadatas": [chunk.to_metadata() for chunk in chunks],
        "texts": [chunk.text for chunk in chunks],
        "titles": [chunk.title for chunk in chunks],
        "bm25": bm25,
    }
    config.BM25_PATH.parent.mkdir(parents=True, exist_ok=True)
    with config.BM25_PATH.open("wb") as handle:
        pickle.dump(payload, handle)


def load_bm25_payload() -> dict[str, Any]:
    """Load the pickled BM25 sidecar."""
    if not config.BM25_PATH.exists():
        raise CorpusError(
            f"BM25 index missing at {config.BM25_PATH}. Run: python -m kestrel.ingest"
        )
    with config.BM25_PATH.open("rb") as handle:
        return pickle.load(handle)


def _reset_index() -> None:
    """Delete any existing Chroma collection so a rebuild starts clean."""
    try:
        import chromadb

        config.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
        client.delete_collection(config.COLLECTION_NAME)
    except Exception:
        # Nothing to delete, or the store was never created.
        pass


def ingest(*, rebuild: bool = False, verbose: bool = True) -> IngestReport:
    """Build (or reuse) the Chroma + BM25 index for the corpus."""
    import time

    started = time.perf_counter()

    if not config.CORPUS_PATH.exists():
        raise CorpusError(f"corpus.jsonl not found at {config.CORPUS_PATH}")

    corpus_sha256, hash_matches = verify_corpus_hash()
    model_name = config.EMBEDDING_MODEL_NAME

    if not rebuild and index_is_current(corpus_sha256, model_name):
        manifest = read_manifest() or {}
        if verbose:
            print(
                f"Index is current (corpus {corpus_sha256[:12]}..., "
                f"{manifest.get('chunk_count')} chunks). Reusing."
            )
        return IngestReport(
            chunks=int(manifest.get("chunk_count", 0)),
            corpus_sha256=corpus_sha256,
            hash_matches=hash_matches,
            embedding_model=model_name,
            reused=True,
            elapsed_s=time.perf_counter() - started,
            paths={
                "chroma": str(config.CHROMA_DIR),
                "bm25": str(config.BM25_PATH),
                "manifest": str(config.MANIFEST_PATH),
            },
        )

    chunks = load_corpus()
    if verbose:
        print(f"Loaded {len(chunks)} chunks from {config.CORPUS_PATH}")

    if rebuild:
        _reset_index()

    embedder = Embedder(model_name)
    if verbose:
        print(f"Embedding with {model_name} (local, first run downloads weights)...")
    vectors = embedder.encode_documents(
        (chunk.text for chunk in chunks), show_progress=verbose
    )
    if verbose:
        print(f"Embedded {len(vectors)} chunks at dim {len(vectors[0])}")

    collection = get_chroma_collection()
    # Replace rather than append, so a rebuild cannot leave stale vectors.
    existing = collection.count()
    if existing:
        _reset_index()
        collection = get_chroma_collection()

    collection.add(
        ids=[chunk.chunk_id for chunk in chunks],
        embeddings=vectors,
        documents=[chunk.text for chunk in chunks],
        metadatas=[chunk.to_metadata() for chunk in chunks],
    )

    if verbose:
        print("Building BM25 index...")
    bm25 = build_bm25(chunks)
    _persist_bm25(chunks, bm25)

    manifest = {
        "corpus_sha256": corpus_sha256,
        "hash_matches_expected": hash_matches,
        "embedding_model": model_name,
        "embedding_dim": len(vectors[0]),
        "chunk_count": len(chunks),
        "chunk_ids": [chunk.chunk_id for chunk in chunks],
        "doc_ids": sorted({chunk.doc_id for chunk in chunks}),
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    config.MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    if verbose:
        print(f"Index written to {config.INDEX_DIR}")

    return IngestReport(
        chunks=len(chunks),
        corpus_sha256=corpus_sha256,
        hash_matches=hash_matches,
        embedding_model=model_name,
        reused=False,
        elapsed_s=time.perf_counter() - started,
        paths={
            "chroma": str(config.CHROMA_DIR),
            "bm25": str(config.BM25_PATH),
            "manifest": str(config.MANIFEST_PATH),
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest corpus.jsonl into Kestrel indexes.")
    parser.add_argument("--rebuild", action="store_true", help="Force a full rebuild.")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output.")
    args = parser.parse_args(argv)

    try:
        report = ingest(rebuild=args.rebuild, verbose=not args.quiet)
    except CorpusError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        f"\nIngestion {'reused existing index' if report.reused else 'complete'}: "
        f"{report.chunks} chunks, sha256 {report.corpus_sha256[:16]}..., "
        f"hash_match={report.hash_matches}, {report.elapsed_s:.1f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())