"""LangSmith observability utilities for the Kestrel multi-agent workflow.

This module is a thin, optional layer:
  * When LangSmith is not configured (no LANGCHAIN_API_KEY or tracing disabled)
    every function degrades gracefully — no imports fail, no exceptions are raised.
  * When LangSmith IS configured, the LangGraph StateGraph automatically sends
    traces for every node invocation.  This module adds:
      - Retrieval-level spans via ``@traceable``
      - Conversation-id and model metadata via ``build_run_config``
      - A verified helper ``get_trace_url`` that queries the LangSmith REST API
        for the real URL and never fabricates one.

Environment variables
---------------------
LANGCHAIN_TRACING_V2   Set to "true" or "1" to enable LangSmith tracing.
LANGCHAIN_API_KEY      LangSmith API key (starts with "ls__...").
LANGCHAIN_PROJECT      Project name (default: "kestrel-research-assistant").
LANGCHAIN_ENDPOINT     Optional custom LangSmith endpoint.

Usage
-----
    from kestrel.tracing import build_run_config, get_trace_url, is_tracing_enabled

    config = build_run_config(conversation_id="conv-abc123")
    state  = graph.invoke(initial, config=config)
    url    = get_trace_url(config.get("run_id"))  # None if not configured
"""

from __future__ import annotations

import os
import uuid
from typing import Any

# Import langsmith Client at module scope so tests can patch 'kestrel.tracing.Client'.
# Falls back to None when langsmith is not installed.
try:
    from langsmith import Client  # type: ignore[import-not-found]
except ImportError:
    Client = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def is_tracing_enabled() -> bool:
    """Return True when LangSmith tracing is fully configured.

    Requires *both*:
      1. ``LANGCHAIN_TRACING_V2`` = "true" or "1" (case-insensitive)
      2. ``LANGCHAIN_API_KEY`` or ``LANGSMITH_API_KEY`` is set and non-empty
    """
    tracing_on = os.environ.get("LANGCHAIN_TRACING_V2", "").lower() in ("true", "1")
    has_key = bool(
        os.environ.get("LANGCHAIN_API_KEY") or os.environ.get("LANGSMITH_API_KEY")
    )
    return tracing_on and has_key


def build_run_config(
    conversation_id: str | None = None,
    *,
    model_name: str | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a LangGraph ``RunnableConfig`` dict with LangSmith metadata.

    A fresh ``run_id`` (UUID4) is generated on every call so each graph
    invocation gets a unique, stable identifier that can later be passed to
    ``get_trace_url``.

    Parameters
    ----------
    conversation_id:
        An opaque string identifying the conversation (e.g. a session ID or
        CLI session UUID).  Included in LangSmith metadata for filtering.
    model_name:
        The LLM model name, e.g. "llama-3.3-70b-versatile".  Included in
        metadata so traces are searchable by model.
    extra_metadata:
        Additional key-value pairs merged into the metadata dict.

    Returns
    -------
    dict
        A dict suitable for passing as ``config=`` to ``graph.invoke()``.
        Contains ``run_id``, ``metadata``, and ``tags``.
    """
    run_id = str(uuid.uuid4())

    metadata: dict[str, Any] = {
        "system": "kestrel-research-assistant",
    }
    if conversation_id:
        metadata["conversation_id"] = conversation_id
    if model_name:
        metadata["model_name"] = model_name
    if extra_metadata:
        metadata.update(extra_metadata)

    return {
        "run_id": run_id,
        "metadata": metadata,
        "tags": ["kestrel"],
    }


def get_trace_url(run_id: str | None) -> str | None:
    """Return the verified LangSmith URL for a graph run, or None.

    This function queries the LangSmith REST API using the ``langsmith`` client
    library.  It never constructs a URL by string interpolation — the URL comes
    directly from the API response.

    Returns ``None`` when:
      * ``run_id`` is None or empty
      * LangSmith tracing is not enabled
      * ``langsmith`` is not installed
      * The run is not yet available (freshly submitted traces may not be
        indexed immediately; callers should not retry in a loop)
      * Any network or authentication error occurs

    Parameters
    ----------
    run_id:
        The ``run_id`` value from ``build_run_config()`` that was passed to
        ``graph.invoke()``.
    """
    if not run_id:
        return None
    if not is_tracing_enabled():
        return None
    if Client is None:
        return None
    try:
        client = Client()
        run = client.read_run(run_id)
        # ``run.url`` is the canonical URL returned by the LangSmith API.
        return getattr(run, "url", None)
    except Exception:
        # Any failure (not configured, network error, run not yet indexed) ->
        # return None rather than raising.
        return None


def traceable_retrieval(name: str = "retrieve_corpus"):
    """Decorator factory that wraps a retrieval function with a LangSmith span.

    When LangSmith is not installed the original function is returned unchanged.
    The decorator is applied at call time (not import time) so it picks up the
    live tracing state.

    Usage::

        @traceable_retrieval(name="bm25_search")
        def my_search_fn(query: str, k: int) -> list:
            ...
    """
    def decorator(fn):  # type: ignore[return]
        try:
            from langsmith import traceable  # type: ignore[import-not-found]

            return traceable(name=name, run_type="retriever")(fn)
        except ImportError:
            return fn

    return decorator


__all__ = [
    "is_tracing_enabled",
    "build_run_config",
    "get_trace_url",
    "traceable_retrieval",
]
