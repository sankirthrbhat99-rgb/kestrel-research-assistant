"""Shared pytest fixtures for the Kestrel test suite."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kestrel import config, ingest, retrieval  # noqa: E402


def _index_available() -> bool:
    if not (config.BM25_PATH.exists() and config.MANIFEST_PATH.exists()):
        return False
    manifest = ingest.read_manifest()
    if not manifest:
        return False
    return manifest.get("corpus_sha256") == ingest.sha256_of_file(config.CORPUS_PATH)


@pytest.fixture(scope="session")
def corpus_chunks():
    """All corpus chunks, loaded fresh from corpus.jsonl."""
    return ingest.load_corpus()


@pytest.fixture(scope="session")
def retriever():
    """A Retriever over the persisted index; skips if the index is stale."""
    if not _index_available():
        pytest.skip("Index missing or stale. Run: python -m kestrel.ingest")
    return retrieval.Retriever()