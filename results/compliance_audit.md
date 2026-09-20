# Kestrel Multi-Agent Research Assistant — Compliance Audit

**Audit date:** 2026-09-20
**Auditor:** Antigravity (automated code + test inspection)
**Python:** 3.14.5 · **pytest:** 9.1.1
**Test result:** 55 / 55 passed (27 s, offline mode, no API key required)

---

## 1. Corpus Integrity

| Check | Result |
|---|---|
| Expected SHA-256 | `b401a4f906446f4e93f1d58c714918acf40d94d81a80c6358e5b7edd46cbbb41` |
| Actual SHA-256 (manifest) | `b401a4f906446f4e93f1d58c714918acf40d94d81a80c6358e5b7edd46cbbb41` |
| Hash match | PASS — `hash_matches_expected: true` |
| Corpus modified by loading | PASS — opened read-only, never written |
| Chunk count | 154 chunks across 25 documents |

`config.py` hard-codes the expected hash and `ingest.py::verify_corpus_hash` warns (never errors)
on mismatch. The test `test_corpus_loads_and_matches_expected_hash` independently confirms this
end-to-end.

---

## 2. Requirement-by-Requirement Verdicts

### 2.1 At Least 3 Agents
**Status: IMPLEMENTED**

Five distinct LangGraph nodes (agents) exist in `agents.py`:

| Node | Function | Role |
|---|---|---|
| `router_node` | Rewrites + classifies + decomposes question | Router / Planner |
| `retriever_node` | Runs BM25/dense/hybrid search per sub-query | Retriever |
| `synthesiser_node` | Drafts answer from evidence; extracts claims | Synthesiser |
| `verifier_node` | Cross-checks each claim against evidence | Verifier / Critic |
| `finaliser_node` | Produces polished user-facing answer | Finaliser |

All five are wired into the LangGraph `StateGraph` in `graph.py`. Tests cover every node
individually.

---

### 2.2 Explicit Typed Shared State
**Status: IMPLEMENTED**

`state.py` defines:

- `KestrelState` — a `TypedDict` with 16 fully-typed fields shared across all nodes
- `EvidenceItem`, `Claim`, `VerifiedClaim`, `Citation` — typed sub-structs
- `make_initial_state()` — factory that zeroes all fields at turn start

Every node receives `KestrelState` and returns a partial dict of only the keys it writes;
LangGraph merges them back. Type annotations use `str`, `list[str]`, `list[EvidenceItem]`, etc.
throughout. The test `test_make_initial_state_all_keys` verifies all required TypedDict keys are
present.

---

### 2.3 Multi-Turn Memory (Conversation History)
**Status: IMPLEMENTED**

- `KestrelState.history: list[dict[str, str]]` carries `[{"role": "user"|"assistant", "content": "..."}]`
- `cli.py` (L114-115) appends each completed turn to `history` and passes it into the next call
- `router_node` formats the last 6 entries (`_format_history`) and injects them into the Router LLM
  prompt so the model can resolve pronouns and ellipsis ("And on Scale?" -> rewritten standalone question)
- Tests `test_graph_follow_up_question` and `test_graph_multi_turn_history_carried` exercise two-turn
  conversations with pronoun resolution and confirm evidence is still retrieved

Minor note: The graph itself is stateless between calls — history persistence is the caller's
responsibility. This matches the documented design and is typical for LangGraph. The CLI loop
correctly accumulates history.

---

### 2.4 Retrieval Before Answering
**Status: IMPLEMENTED**

The graph topology enforces this:

```
START -> router_node -> [retrieval path] -> retriever_node -> synthesiser_node -> verifier_node -> finaliser_node -> END
```

`synthesiser_node` only reads `state["evidence"]` — it has no code path to answer without it.
If `evidence` is empty, it returns `OFFLINE_NO_EVIDENCE` verbatim. The `finaliser_node` also
checks `if not evidence: return OFFLINE_NO_EVIDENCE`.

The chit_chat/off_topic short-circuit bypasses retrieval entirely (correct behaviour).
Test `test_graph_chit_chat_short_circuits` confirms `state["evidence"] == []` for chit_chat.

---

### 2.5 Local Embeddings
**Status: IMPLEMENTED**

`ingest.py` `Embedder` class:

- Model: `BAAI/bge-small-en-v1.5` (configured in `config.py`)
- Library: `sentence-transformers >= 6.1.0`
- Cached locally under `.model_cache/` (inside workspace, not `~/.cache`)
- `encode_documents()` — no query instruction prefix (correct per bge docs)
- `encode_query()` — applies `QUERY_INSTRUCTION` prefix on query side only (correct)
- `normalize_embeddings=True` — produces unit-norm vectors compatible with Chroma's cosine space

Manifest confirms: `"embedding_model": "BAAI/bge-small-en-v1.5"`, `"embedding_dim": 384`.
No external API is called at query time.

---

### 2.6 Chroma Persistent Local Vector Store
**Status: IMPLEMENTED**

- `chromadb.PersistentClient(path=str(config.CHROMA_DIR))` — writes to `index/chroma/` inside workspace
- Collection name: `kestrel_corpus`, cosine space (`{"hnsw:space": "cosine"}`)
- Survives process exit; manifest guards against re-ingestion
- `Retriever.collection` lazy-loads via `get_chroma_collection()`
- `dense_search()` calls `collection.query()` and converts L2 cosine distance to similarity (`1.0 - distance`)

---

### 2.7 BM25 / Hybrid Retrieval
**Status: IMPLEMENTED**

Three strategies are all working (tested):

| Strategy | Implementation |
|---|---|
| `bm25` | `rank_bm25.BM25Okapi` over tokenized chunk texts, pickled to `index/bm25.pkl` |
| `dense` | Chroma cosine similarity (default / Phase 1 baseline) |
| `hybrid` | BM25 + dense fused with Reciprocal Rank Fusion (RRF, k=60) |

RRF fusion is implemented in `rrf_fuse()` with correct score formula `1/(rrf_k + rank)`.
Tests `test_hybrid_records_both_retrievers` and `test_rrf_fusion_math` confirm both strategies
contribute and the math is correct. Deduplication (`dedupe()`) merges provenance across retrievers.

---

### 2.8 Claim-Level Verifier Verdicts
**Status: IMPLEMENTED**

`verifier_node` in `agents.py` and `VERIFIER_SYSTEM` in `prompts.py`:

- Receives `claims: list[Claim]` (each claim is a single factual assertion with `chunk_ids`)
- LLM assigns one of four per-claim verdicts: `supported`, `partially_supported`,
  `conflicting_evidence`, `insufficient_evidence`
- Returns `verified_claims: list[VerifiedClaim]` — each with `claim`, `verdict`, `chunk_ids`, `reason`
- Top-level `verification_verdict` is the most severe across all claims (severity ordering:
  `insufficient_evidence > conflicting_evidence > partially_supported > supported`)
- `VerifiedClaim` TypedDict is defined in `state.py`

The offline path marks everything `supported` (correct — nothing to cross-check without an LLM).
Tests verify offline verdicts, structure, and that `verifier_node` with no claims returns
`verified_claims == []`.

---

### 2.9 Conflicting Evidence Handling with Date/Version Comparison
**Status: PARTIAL**

What exists:

The `VERIFIER_SYSTEM` prompt (lines 108-112 of `prompts.py`) explicitly instructs the model:

  "When sources conflict, compare their 'published' date (YYYYMMDD) and 'version' metadata and
  say which source is newer. Do not treat a superseded release note as current."

The `FINALIZER_SYSTEM` prompt instructs:

  "If 'conflicting_evidence', present the conflict, state which source is newer using its
  published date and version, and say what the current behaviour is believed to be."

Metadata fields `published` (YYYYMMDD) and `version` are persisted per chunk in Chroma and the
BM25 sidecar. `_format_metadata()` in `agents.py` formats them into the Finaliser prompt.

Gap:

- There is no deterministic/offline code that implements date-comparison logic — the offline
  verifier marks everything `supported` and the offline finaliser simply trims the draft. The
  conflict-handling behaviour is fully LLM-dependent.
- No test exercises a conflicting-evidence scenario end-to-end (no offline tests forcing a
  `conflicting_evidence` verdict).
- The requirement is satisfied at the prompt/schema level but has no offline fallback and
  no test coverage for the conflicting path.

---

### 2.10 Unsupported Question Handling
**Status: IMPLEMENTED**

Multiple layers handle this:

1. Router: classifies `off_topic` -> short-circuits to `finaliser_node`, returns `OFFLINE_OFF_TOPIC`
2. Synthesiser: if `evidence == []` -> returns `OFFLINE_NO_EVIDENCE` (no guessing)
3. Finaliser: if `evidence == []` -> returns `OFFLINE_NO_EVIDENCE`
4. LLM prompts: `SYNTHESIS_SYSTEM` forbids guessing; `FINALIZER_SYSTEM` instructs to say plainly
   when evidence is absent

Tests: `test_synthesiser_offline_no_evidence`, `test_finaliser_no_evidence_returns_no_evidence_message`,
`test_graph_unknown_question_returns_no_evidence_message` all pass.

---

### 2.11 Maximum One Retry
**Status: PARTIAL**

What exists:

Each agent node has a `try/except (LLMNotConfigured, RuntimeError, ValueError)` block that falls
back to the offline/heuristic path on any error. This is a single-attempt + offline-fallback pattern.

Gap:

There is no retry loop in any agent node. The `LLMClient.complete()` method (in `llm.py`) makes
a single `urllib.request.urlopen()` call with no retry or backoff. If a `429 Too Many Requests` or
transient network error occurs, the exception propagates up and the node falls back to offline
immediately — it does not retry the LLM call once before giving up.

A "maximum one retry" requirement means: attempt -> if 429/5xx -> wait (backoff) -> retry once ->
if still failing, fallback. This specific pattern is not implemented.

---

### 2.12 Sequential LLM Calls
**Status: IMPLEMENTED**

The graph topology enforces strict sequential execution:

```
router -> retriever -> synthesiser -> verifier -> finaliser
```

Each node is added with `add_edge` (not parallel branches), so nodes execute one at a time. Only
one node calls the LLM per step. The `LLMClient` is a synchronous `urllib` client with no async
methods.

---

### 2.13 429 Retry / Backoff
**Status: MISSING**

`llm.py::LLMClient.complete()` catches `urllib.error.HTTPError` and raises a `RuntimeError`
immediately — there is no inspection of `exc.code` to detect `429`, and no sleep/backoff/retry
logic. The agent nodes catch the `RuntimeError` and fall back to offline mode on first failure.

Current code (llm.py L123-125) — no 429 handling:

```python
except urllib.error.HTTPError as exc:  # pragma: no cover - network path
    detail = exc.read().decode("utf-8", errors="replace")
    raise RuntimeError(f"LLM request failed ({exc.code}): {detail}") from exc
```

This is the most significant gap against the assignment requirements.

---

### 2.14 LangGraph Orchestration
**Status: IMPLEMENTED**

`graph.py` uses `langgraph.graph.StateGraph`:

- `StateGraph(KestrelState)` — typed state
- Five nodes registered with `builder.add_node()`
- `add_edge(START, "router")`
- `add_conditional_edges("router", route_after_router, {"retrieve": "retriever", "finalise": "finaliser"})`
- Linear edges: `retriever -> synthesiser -> verifier -> finaliser -> END`
- `builder.compile()` produces a runnable graph
- `run_query()` calls `graph.invoke(initial_state)` and returns final `KestrelState`

Package: `langgraph >= 0.2.0, < 1.0` in requirements. Confirmed working — 12 full-graph tests pass.

---

### 2.15 CLI Interface
**Status: IMPLEMENTED**

`cli.py` provides:

- `python -m kestrel.cli` entry point
- Interactive REPL loop (`input("You: ")`)
- Displays `[route:]`, `[verification:]`, answer, and `Sources: [chunk_id] title`
- Handles `quit`/`exit`/`q` and `clear` (resets history)
- Multi-turn history accumulated across turns
- Graceful `EOFError`/`KeyboardInterrupt` handling
- Works in offline mode (no API key needed)

---

## 3. Summary Table

| # | Requirement | Status | Evidence |
|---|---|---|---|
| 1 | At least 3 agents | IMPLEMENTED | 5 nodes: router, retriever, synthesiser, verifier, finaliser |
| 2 | Explicit typed shared state | IMPLEMENTED | `KestrelState` TypedDict, 4 sub-structs, `make_initial_state()` |
| 3 | Multi-turn memory | IMPLEMENTED | `history` field, CLI accumulates turns, router uses history in prompt |
| 4 | Retrieval before answering | IMPLEMENTED | Graph topology enforces it; synthesiser/finaliser refuse without evidence |
| 5 | Local embeddings | IMPLEMENTED | `BAAI/bge-small-en-v1.5` via sentence-transformers, cached in `.model_cache/` |
| 6 | Chroma persistent local vector store | IMPLEMENTED | `PersistentClient` writing to `index/chroma/`, cosine space |
| 7 | BM25 / hybrid retrieval | IMPLEMENTED | BM25Okapi + dense + RRF hybrid; all three strategies tested |
| 8 | Claim-level verifier verdicts | IMPLEMENTED | 4 per-claim verdicts, `VerifiedClaim` struct, severity ordering |
| 9 | Conflicting evidence with date/version | PARTIAL | Prompt instructs it; metadata carried; no offline code path; no test |
| 10 | Unsupported question handling | IMPLEMENTED | `OFFLINE_NO_EVIDENCE`, off_topic route, LLM prompts forbid guessing |
| 11 | Maximum one retry | PARTIAL | Offline fallback on error exists; no actual retry loop implemented |
| 12 | Sequential LLM calls | IMPLEMENTED | Linear graph edges, synchronous client, no parallelism |
| 13 | 429 retry / backoff | MISSING | `HTTPError` raises immediately; no 429 detection, no sleep, no retry |
| 14 | LangGraph orchestration | IMPLEMENTED | `StateGraph`, conditional edges, `compile()`, `invoke()` |
| 15 | CLI interface | IMPLEMENTED | Interactive REPL, history, citations, offline-capable |

**Score: 12 IMPLEMENTED — 2 PARTIAL — 1 MISSING**

---

## 4. Gap Analysis and Priorities

### Priority 1 (Blocking — clear assignment requirement) — 429 Retry / Backoff

File: `kestrel/llm.py`

`LLMClient.complete()` needs:
1. Detect `exc.code == 429` (or 5xx) in the `HTTPError` handler
2. Sleep (exponential backoff: e.g., 2s -> 4s)
3. Retry once (matching the "maximum one retry" requirement)
4. On second failure, re-raise so the agent node's `except` catches it and falls back offline

Minimal change — isolated to ~15 lines in `llm.py`. No existing tests need to be deleted; new tests
should mock `urllib.request.urlopen`. Fixing Priority 1 also closes requirement 2.11 (maximum one retry)
simultaneously.

### Priority 2 (Partial -> Implemented) — Conflicting Evidence Tests

File: New test cases in `tests/test_agents.py`

The metadata infrastructure and prompts are in place. What's missing:
- A test that crafts a state with two `EvidenceItem`s having different `version`/`published` values
  and a claim that conflicts between them
- A mock LLM response returning `verdict: "conflicting_evidence"` and a `reason` citing the newer source
- Verification that `finaliser_node` surfaces the conflict to the user

This does not require an API key — the mock LLM path can inject the response directly.

### Priority 3 (Minor documentation gap)

The "maximum one retry" in requirement 11 most naturally means: one retry per LLM call in
`LLMClient.complete()`. The Priority 1 fix satisfies this interpretation and closes the gap.

---

## 5. What Is Working Correctly

- Corpus SHA-256 verified and matches expected hash exactly
- 154 chunks indexed, all 25 doc_ids present
- All three retrieval strategies return correct results with deduplication
- RRF fusion math is correct (`1/(60 + rank)`)
- Full graph runs end-to-end with no API key (offline fallback)
- Follow-up questions with pronoun resolution work via history
- Chit_chat and off_topic short-circuits skip retrieval correctly
- Per-claim verdict structure is fully typed
- Metadata fields (`published`, `version`) persisted and available to verifier/finaliser
- 55/55 tests pass in 27 seconds

---

## 6. Files Inspected

| File | Lines | Purpose |
|---|---|---|
| `kestrel/state.py` | 164 | TypedDict state, sub-structs |
| `kestrel/agents.py` | 487 | All 5 node functions + helpers |
| `kestrel/graph.py` | 134 | LangGraph wiring |
| `kestrel/retrieval.py` | 391 | dense/BM25/hybrid search, RRF |
| `kestrel/llm.py` | 135 | LLM client (urllib) |
| `kestrel/prompts.py` | 209 | All prompt templates |
| `kestrel/ingest.py` | 450 | Corpus load, embed, Chroma/BM25 build |
| `kestrel/config.py` | 180 | All configuration, SHA-256 |
| `kestrel/cli.py` | 120 | Interactive CLI |
| `tests/test_agents.py` | 575 | 33 agent/graph tests |
| `tests/test_retrieval.py` | 262 | 22 retrieval tests |
| `tests/conftest.py` | 37 | Shared fixtures |
| `requirements.txt` | 28 | All dependencies |
| `index/manifest.json` | 191 | Built index metadata |
