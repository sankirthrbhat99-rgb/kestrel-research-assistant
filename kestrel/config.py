"""Central configuration for the Kestrel Multi-Agent Research Assistant.

Phase 1 scope: ingestion + retrieval settings only. Agent/LLM settings exist so
later phases can extend this module without changing the Phase 1 surface.

All paths are derived from the repository root so that every artifact the
pipeline writes (Chroma store, BM25 index, model cache, results) stays inside
the workspace. This matters because the execution sandbox only permits writes
under the workspace, and library defaults would otherwise target the user home
directory.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

ROOT: Path = Path(__file__).resolve().parent.parent

CORPUS_PATH: Path = Path(os.environ.get("KESTREL_CORPUS_PATH", ROOT / "corpus.jsonl"))
INDEX_DIR: Path = Path(os.environ.get("KESTREL_INDEX_DIR", ROOT / "index"))
CHROMA_DIR: Path = INDEX_DIR / "chroma"
BM25_PATH: Path = INDEX_DIR / "bm25.pkl"
MANIFEST_PATH: Path = INDEX_DIR / "manifest.json"
COLLECTION_NAME: str = "kestrel_corpus"

RESULTS_DIR: Path = ROOT / "results"

# Model caches must live inside the workspace: HuggingFace and Torch default to
# the user home directory, which the sandbox denies.
MODEL_CACHE_DIR: Path = ROOT / ".model_cache"
os.environ.setdefault("HF_HOME", str(MODEL_CACHE_DIR / "huggingface"))
os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", str(MODEL_CACHE_DIR / "sentence_transformers"))
os.environ.setdefault("TORCH_HOME", str(MODEL_CACHE_DIR / "torch"))

# huggingface_hub probes symlink support by writing into a temporary directory
# it creates with mode 0700. Restricted sandboxes (this one included) deny
# writes into such directories, which makes the probe raise PermissionError and
# aborts the model download. Disabling symlinks skips the probe entirely;
# Windows uses copies instead of links in the cache regardless.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

# Pre-create every cache directory at import time. Creating them from Python
# works because these are ordinary directories rather than mkdtemp's 0700 ones.
for _cache_dir in (
    MODEL_CACHE_DIR,
    MODEL_CACHE_DIR / "huggingface",
    MODEL_CACHE_DIR / "sentence_transformers",
    MODEL_CACHE_DIR / "torch",
):
    _cache_dir.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------
# Corpus integrity
# --------------------------------------------------------------------------

# Expected SHA-256 of corpus.jsonl. No value was supplied with the assignment
# brief, so this is the digest of the provided corpus as delivered. Override
# with the KESTREL_CORPUS_SHA256 environment variable if the brief specifies a
# different digest. A mismatch warns rather than aborts, so a legitimately
# updated corpus can still be ingested deliberately.
EXPECTED_CORPUS_SHA256: str = os.environ.get(
    "KESTREL_CORPUS_SHA256",
    "b401a4f906446f4e93f1d58c714918acf40d94d81a80c6358e5b7edd46cbbb41",
).lower()

# --------------------------------------------------------------------------
# Embeddings
# --------------------------------------------------------------------------

EMBEDDING_MODEL_NAME: str = os.environ.get(
    "KESTREL_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"
)

# bge models are trained with an instruction prefix on the query side only.
# Applying it to the query (not the documents) is the documented usage.
QUERY_INSTRUCTION: str = os.environ.get(
    "KESTREL_QUERY_INSTRUCTION",
    "Represent this sentence for searching relevant passages: ",
)

# --------------------------------------------------------------------------
# Retrieval
# --------------------------------------------------------------------------

# "dense" is the Phase 1 baseline; "hybrid" fuses BM25 and dense with RRF.
DEFAULT_STRATEGY: str = os.environ.get("KESTREL_STRATEGY", "hybrid").lower()
VALID_STRATEGIES: tuple[str, ...] = ("dense", "bm25", "hybrid")

DEFAULT_K: int = 6
# Candidate pool pulled from each retriever before fusion/dedupe.
DEFAULT_CANDIDATES: int = 20
# Reciprocal Rank Fusion constant (Cormack et al. use 60).
RRF_K: int = 60
# Neighbour (adjacent-chunk) expansion is off by default for the baseline.
NEIGHBOR_EXPANSION_DEFAULT: bool = False


@dataclass(frozen=True)
class RetrievalSettings:
    """Resolved retrieval parameters for a single call."""

    strategy: str = DEFAULT_STRATEGY
    k: int = DEFAULT_K
    candidates: int = DEFAULT_CANDIDATES
    rrf_k: int = RRF_K
    expand_neighbors: bool = NEIGHBOR_EXPANSION_DEFAULT
    neighbor_window: int = 1

    def __post_init__(self) -> None:
        if self.strategy not in VALID_STRATEGIES:
            raise ValueError(
                f"Unknown strategy {self.strategy!r}; expected one of {VALID_STRATEGIES}"
            )
        if self.k < 1:
            raise ValueError("k must be >= 1")
        if self.candidates < self.k:
            # Pull at least k candidates from every retriever.
            object.__setattr__(self, "candidates", self.k)


@dataclass(frozen=True)
class MetadataFields:
    """Metadata fields persisted per chunk (from corpus.jsonl plus derived)."""

    carried: tuple[str, ...] = (
        "doc_id",
        "title",
        "category",
        "owner",
        "source_url",
        "published",
        "version",
    )
    derived: tuple[str, ...] = ("chunk_index", "ordinal")
    all_fields: tuple[str, ...] = field(
        default=(
            "doc_id",
            "title",
            "category",
            "owner",
            "source_url",
            "published",
            "version",
            "chunk_index",
            "ordinal",
        )
    )


METADATA = MetadataFields()

__all__ = [
    "ROOT",
    "CORPUS_PATH",
    "INDEX_DIR",
    "CHROMA_DIR",
    "BM25_PATH",
    "MANIFEST_PATH",
    "COLLECTION_NAME",
    "RESULTS_DIR",
    "MODEL_CACHE_DIR",
    "EXPECTED_CORPUS_SHA256",
    "EMBEDDING_MODEL_NAME",
    "QUERY_INSTRUCTION",
    "DEFAULT_STRATEGY",
    "VALID_STRATEGIES",
    "DEFAULT_K",
    "DEFAULT_CANDIDATES",
    "RRF_K",
    "NEIGHBOR_EXPANSION_DEFAULT",
    "RetrievalSettings",
    "METADATA",
]