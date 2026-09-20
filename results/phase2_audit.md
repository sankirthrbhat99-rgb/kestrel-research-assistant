# Phase 2 Gap Audit

## 1. Requirements Checklist

| Requirement | Status | Notes |
|---|---|---|
| **Multi-agent architecture & shared state** | COMPLETE | Router, Retriever, Synthesiser, Verifier, and Finaliser exist as LangGraph nodes. Shared `KestrelState` TypedDict is implemented. |
| **Retrieval quality and hybrid search** | COMPLETE | `hybrid` strategy (BM25 + dense) is implemented in `retrieval.py` with Reciprocal Rank Fusion and optional neighbour expansion. |
| **Citation tracking and validation** | COMPLETE | Synthesiser cites inline (`[chunk_id]`). Verifier evaluates every claim. |
| **Verifier and finalizer behavior** | MISSING | Verifier checks conflicting evidence by date. However, the required retry loop (`verifier` -> `retriever` if `retries < 1` and evidence is insufficient) is missing from the graph topology and state. |
| **Unsupported questions and conflicting evidence** | COMPLETE | Finaliser handles `insufficient_evidence` and `conflicting_evidence` cleanly, comparing dates/versions as instructed. |
| **Conversation history/memory** | COMPLETE | Router rewrites follow-up questions using `history`. |
| **LangSmith tracing and metadata** | COMPLETE | `@traceable` applied to retriever, full graph traces enabled via config. |
| **CLI and Streamlit compatibility** | COMPLETE | `chat.py` works, `stream_question` implemented for Streamlit. |

## 2. Highest Impact Missing Implementation
The only major gap for Phase 2 is the **Verifier -> Retriever Retry Loop**. 

I am implementing this immediately by:
1. Adding `retries: int` to `KestrelState`.
2. Modifying `VERIFIER_SYSTEM` prompt to request a `"refined_query"` when evidence is lacking.
3. Adding conditional routing logic (`route_after_verifier`) in `agents.py`.
4. Wiring the conditional edge back to `retriever` in `graph.py`.

This fulfills the multi-agent critique-and-refine requirement without breaking any existing baseline evaluations.
