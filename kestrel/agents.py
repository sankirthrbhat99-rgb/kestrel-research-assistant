"""Agent nodes for the Kestrel multi-agent LangGraph workflow.

Each public function in this module is a LangGraph node: it receives a
``KestrelState`` dict and returns a *partial* dict with only the keys it
writes.  LangGraph merges the partial update back into the running state.

Offline fallback (no API key)
------------------------------
Every node has a deterministic offline path that does NOT call an LLM.
When ``LLMConfig.configured`` is False the node uses rule-based heuristics
instead.  This guarantees the full graph can run -- and the CLI/tests can
exercise it -- with zero credentials.

The offline router uses keyword matching; the offline synthesiser builds a
plain-text answer from the top retrieved chunks; the offline verifier marks
everything "supported" (it has nothing to compare against); the offline
finaliser trims the draft to a clean paragraph.

JSON parsing
------------
Every LLM agent that returns JSON wraps its call in a try/except that falls
back to the offline path if the model returns unparseable output.  A bad
completion degrades quality but never raises an unhandled exception.

LangSmith tracing
-----------------
Retrieval calls are wrapped with ``@traceable(run_type="retriever")`` when
LangSmith is configured.  The decorator is applied lazily so that importing
this module never fails when langsmith is absent.  Every LLM call is a child
run of its parent node span, automatically captured by LangGraph's built-in
LangSmith integration.
"""

from __future__ import annotations

import json
import re
from typing import Any

from . import config
from .llm import LLMClient, LLMConfig, LLMNotConfigured
from .prompts import (
    OFFLINE_CHIT_CHAT,
    OFFLINE_NO_EVIDENCE,
    OFFLINE_OFF_TOPIC,
    FINALIZER_SYSTEM,
    FINALIZER_USER,
    ROUTER_SYSTEM,
    ROUTER_USER,
    SYNTHESIS_SYSTEM,
    SYNTHESIS_USER,
    VERIFIER_SYSTEM,
    VERIFIER_USER,
    render,
)
from .retrieval import Retriever, SearchResult, get_retriever
from .state import (
    Citation,
    Claim,
    EvidenceItem,
    KestrelState,
    VerifiedClaim,
)
from .tracing import traceable_retrieval


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

_KESTREL_KEYWORDS = re.compile(
    r"\b(kestrel|beacon|funnel|cohort|trail|kql|warehouse|sync|redshift|"
    r"bigquery|snowflake|plan|starter|growth|scale|api|sdk|retention|"
    r"gdpr|onboarding|incident|outage|postmortem|runbook|query|timeout|"
    r"limit|rate|throttl|pricing|feature|analytic|event|session|user)\b",
    re.IGNORECASE,
)

_CHIT_CHAT_KEYWORDS = re.compile(
    r"\b(hello|hi|hey|thanks|thank you|great|bye|goodbye|who are you|"
    r"what can you|help me|how do you)\b",
    re.IGNORECASE,
)


def _format_history(history: list[dict[str, str]]) -> str:
    if not history:
        return "(none)"
    lines: list[str] = []
    for turn in history[-6:]:  # keep last 3 pairs
        role = turn.get("role", "user").capitalize()
        lines.append(f"{role}: {turn.get('content', '')}")
    return "\n".join(lines)


def _format_evidence(evidence: list[EvidenceItem]) -> str:
    if not evidence:
        return "(no evidence retrieved)"
    parts: list[str] = []
    for item in evidence:
        parts.append(
            f"[{item['chunk_id']}] (title: {item['title']}, score: {item['score']:.3f})\n"
            f"{item['text']}"
        )
    return "\n\n".join(parts)


def _format_metadata(evidence: list[EvidenceItem]) -> str:
    if not evidence:
        return "(none)"
    rows: list[str] = []
    for item in evidence:
        m = item.get("metadata", {})
        rows.append(
            f"chunk_id={item['chunk_id']!r} title={item['title']!r} "
            f"version={m.get('version', '')!r} published={m.get('published', '')!r}"
        )
    return "\n".join(rows)


def _format_claims(claims: list[Claim]) -> str:
    if not claims:
        return "(no claims extracted)"
    return json.dumps(claims, indent=2)


def _safe_json(text: str) -> dict[str, Any] | None:
    """Try to parse a JSON object from ``text``; return None on failure."""
    text = text.strip()
    # Strip markdown fences like ```json ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract the first {...} object from the text (models sometimes
        # add a trailing explanation after the JSON).
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return None


def _search_results_to_evidence(results: list[SearchResult]) -> list[EvidenceItem]:
    return [
        EvidenceItem(
            chunk_id=r.chunk_id,
            title=r.title,
            text=r.text,
            score=r.score,
            doc_id=r.doc_id,
            metadata=dict(r.metadata),
        )
        for r in results
    ]


def _get_client() -> tuple[LLMClient, bool]:
    """Return (client, is_configured).  Client is always returned even when
    unconfigured so nodes can choose their offline path."""
    client = LLMClient()
    return client, client.config.configured


# --------------------------------------------------------------------------
# Node: Router / Planner
# --------------------------------------------------------------------------


def _offline_router(question: str, history: list[dict[str, str]]) -> dict[str, Any]:
    """Keyword-based heuristic routing when no LLM is configured."""
    if _CHIT_CHAT_KEYWORDS.search(question) and not _KESTREL_KEYWORDS.search(question):
        route = "chit_chat"
        sub_queries: list[str] = []
        reasoning = "Offline: matched chit_chat keywords, no Kestrel keywords."
    elif _KESTREL_KEYWORDS.search(question):
        route = "retrieval"
        sub_queries = [question]
        reasoning = "Offline: matched Kestrel keywords."
    else:
        # Be generous: when in doubt, try retrieval.
        route = "retrieval"
        sub_queries = [question]
        reasoning = "Offline: no strong signal; defaulting to retrieval."
    return {
        "standalone_question": question,  # no rewrite offline
        "route": route,
        "sub_queries": sub_queries,
        "router_reasoning": reasoning,
    }


def router_node(state: KestrelState) -> dict[str, Any]:
    """Rewrite, classify (retrieval / chit_chat / off_topic) and decompose."""
    question = state["question"]
    history = state["history"]

    client, configured = _get_client()

    if not configured:
        return _offline_router(question, history)

    prompt = render(ROUTER_USER, history=_format_history(history), question=question)
    try:
        raw = client.complete(prompt, system=ROUTER_SYSTEM, temperature=0.0)
        parsed = _safe_json(raw)
        if not parsed:
            raise ValueError(f"Unparseable router output: {raw!r}")
        return {
            "standalone_question": str(parsed.get("standalone_question", question)),
            "route": str(parsed.get("route", "retrieval")),
            "sub_queries": list(parsed.get("sub_queries", [question])),
            "router_reasoning": str(parsed.get("reasoning", "")),
        }
    except (LLMNotConfigured, RuntimeError, ValueError):
        return _offline_router(question, history)


# --------------------------------------------------------------------------
# Node: Retriever
# --------------------------------------------------------------------------


@traceable_retrieval(name="kestrel_retriever")
def _traced_search(
    retriever: Retriever,
    query: str,
    k: int,
    strategy: str,
) -> list[SearchResult]:
    """Single-query corpus search wrapped with a LangSmith retriever span."""
    return retriever.search_corpus(query, k=k, strategy=strategy)


def retriever_node(
    state: KestrelState,
    retriever: Retriever | None = None,
) -> dict[str, Any]:
    """Run search_corpus for every sub-query and merge evidence."""
    sub_queries = state.get("sub_queries") or [state["standalone_question"] or state["question"]]
    _retriever = retriever or get_retriever()

    seen_ids: set[str] = set()
    merged: list[EvidenceItem] = []

    for q in sub_queries:
        if not q or not q.strip():
            continue
        results = _traced_search(
            _retriever,
            q,
            k=config.DEFAULT_K,
            strategy=config.DEFAULT_STRATEGY,
        )
        for item in _search_results_to_evidence(results):
            if item["chunk_id"] not in seen_ids:
                seen_ids.add(item["chunk_id"])
                merged.append(item)

    # Re-sort by score descending after merge.
    merged.sort(key=lambda x: x["score"], reverse=True)

    return {"evidence": merged}


# --------------------------------------------------------------------------
# Node: Synthesiser
# --------------------------------------------------------------------------


def _offline_synthesiser(
    question: str, evidence: list[EvidenceItem]
) -> dict[str, Any]:
    """Build a plain-text draft from the top retrieved chunks."""
    if not evidence:
        return {
            "draft_answer": OFFLINE_NO_EVIDENCE,
            "claims": [],
            "missing_evidence": "No evidence was retrieved for this question.",
        }
    top = evidence[:4]
    bullet_parts = [f"• [{item['chunk_id']}] {item['text'][:300].strip()}" for item in top]
    # «[OFFLINE]» prefix distinguishes deterministic answers from real LLM answers.
    draft = (
        "[OFFLINE] Based on the knowledge base (no LLM configured):\n\n"
        + "\n\n".join(bullet_parts)
    )
    claims: list[Claim] = [
        {"claim": item["text"][:120].strip(), "chunk_ids": [item["chunk_id"]]}
        for item in top
    ]
    return {
        "draft_answer": draft,
        "claims": claims,
        "missing_evidence": "",
    }


def synthesiser_node(state: KestrelState) -> dict[str, Any]:
    """Draft an answer from the retrieved evidence."""
    question = state["standalone_question"] or state["question"]
    evidence = state["evidence"]

    client, configured = _get_client()

    if not configured:
        return _offline_synthesiser(question, evidence)

    evidence_text = _format_evidence(evidence)
    prompt = render(SYNTHESIS_USER, question=question, evidence=evidence_text)
    try:
        raw = client.complete(prompt, system=SYNTHESIS_SYSTEM, temperature=0.0)
        parsed = _safe_json(raw)
        if not parsed:
            raise ValueError(f"Unparseable synthesiser output: {raw!r}")
        return {
            "draft_answer": str(parsed.get("draft_answer", "")),
            "claims": list(parsed.get("claims", [])),
            "missing_evidence": str(parsed.get("missing_evidence", "")),
        }
    except (LLMNotConfigured, RuntimeError, ValueError):
        return _offline_synthesiser(question, evidence)


# --------------------------------------------------------------------------
# Node: Verifier / Critic
# --------------------------------------------------------------------------


def _offline_verifier(
    claims: list[Claim], evidence: list[EvidenceItem], draft: str
) -> dict[str, Any]:
    """Mark every claim 'supported' offline (we cannot cross-check without an LLM)."""
    verified: list[VerifiedClaim] = [
        VerifiedClaim(
            claim=c["claim"],
            verdict="supported",
            chunk_ids=c["chunk_ids"],
            reason="Offline: assumed supported (no LLM to verify).",
        )
        for c in claims
    ]
    return {
        "verified_claims": verified,
        "verification_verdict": "supported",
        "verification_notes": "Offline mode: no LLM verification performed.",
    }


def verifier_node(state: KestrelState) -> dict[str, Any]:
    """Cross-check every claim against the retrieved evidence."""
    question = state["standalone_question"] or state["question"]
    draft = state["draft_answer"]
    claims = state["claims"]
    evidence = state["evidence"]

    client, configured = _get_client()

    if not configured or not claims:
        return _offline_verifier(claims, evidence, draft)

    prompt = render(
        VERIFIER_USER,
        question=question,
        draft=draft,
        claims=_format_claims(claims),
        evidence=_format_evidence(evidence),
    )
    try:
        raw = client.complete(prompt, system=VERIFIER_SYSTEM, temperature=0.0)
        parsed = _safe_json(raw)
        if not parsed:
            raise ValueError(f"Unparseable verifier output: {raw!r}")

        raw_claims = parsed.get("claims", [])
        verified: list[VerifiedClaim] = []
        for c in raw_claims:
            verified.append(
                VerifiedClaim(
                    claim=str(c.get("claim", "")),
                    verdict=str(c.get("verdict", "supported")),
                    chunk_ids=list(c.get("chunk_ids", [])),
                    reason=str(c.get("reason", "")),
                )
            )

        # Severity ordering for the top-level verdict.
        _ORDER = {
            "insufficient_evidence": 4,
            "conflicting_evidence": 3,
            "partially_supported": 2,
            "supported": 1,
        }
        final_verdict = str(parsed.get("verdict", worst))
        out: dict[str, Any] = {
            "verified_claims": verified,
            "verification_verdict": final_verdict,
            "verification_notes": str(parsed.get("notes", "")),
        }
        
        refined = str(parsed.get("refined_query", "")).strip()
        if (final_verdict == "insufficient_evidence" or any(c["verdict"] in ("insufficient_evidence", "partially_supported") for c in verified)) and refined and state.get("retries", 0) < 1:
            out["retries"] = state.get("retries", 0) + 1
            out["sub_queries"] = state.get("sub_queries", []) + [refined]
            
        return out
    except (LLMNotConfigured, RuntimeError, ValueError):
        return _offline_verifier(claims, evidence, draft)


# --------------------------------------------------------------------------
# Node: Finaliser
# --------------------------------------------------------------------------


def _offline_finaliser(
    route: str,
    draft: str,
    evidence: list[EvidenceItem],
    verdict: str,
) -> dict[str, Any]:
    """Produce the final answer offline."""
    if route == "chit_chat":
        return {"final_answer": OFFLINE_CHIT_CHAT, "citations": []}
    if route == "off_topic":
        return {"final_answer": OFFLINE_OFF_TOPIC, "citations": []}
    if not draft or not evidence:
        return {"final_answer": OFFLINE_NO_EVIDENCE, "citations": []}

    # Trim the draft to a readable length.
    answer = draft[:2000].strip()
    citations: list[Citation] = [
        Citation(chunk_id=item["chunk_id"], title=item["title"])
        for item in evidence[:6]
    ]
    return {"final_answer": answer, "citations": citations}


def finaliser_node(state: KestrelState) -> dict[str, Any]:
    """Produce the polished, user-facing answer."""
    route = state["route"]
    question = state["standalone_question"] or state["question"]
    draft = state["draft_answer"]
    verdict = state["verification_verdict"] or "supported"
    notes = state["verification_notes"]
    evidence = state["evidence"]

    # Short-circuits that need no LLM.
    if route in ("chit_chat", "off_topic"):
        return _offline_finaliser(route, draft, evidence, verdict)

    if not evidence:
        return {"final_answer": OFFLINE_NO_EVIDENCE, "citations": []}

    client, configured = _get_client()

    if not configured:
        return _offline_finaliser(route, draft, evidence, verdict)

    metadata_text = _format_metadata(evidence)
    prompt = render(
        FINALIZER_USER,
        question=question,
        verdict=verdict,
        notes=notes,
        draft=draft,
        metadata=metadata_text,
    )
    try:
        raw = client.complete(prompt, system=FINALIZER_SYSTEM, temperature=0.0)
        parsed = _safe_json(raw)
        if not parsed:
            raise ValueError(f"Unparseable finaliser output: {raw!r}")
        raw_citations = parsed.get("citations", [])
        citations: list[Citation] = [
            Citation(chunk_id=str(c.get("chunk_id", "")), title=str(c.get("title", "")))
            for c in raw_citations
        ]
        return {
            "final_answer": str(parsed.get("final_answer", draft)),
            "citations": citations,
        }
    except (LLMNotConfigured, RuntimeError, ValueError):
        return _offline_finaliser(route, draft, evidence, verdict)


# --------------------------------------------------------------------------
# Routing logic (used by the graph conditional edge)
# --------------------------------------------------------------------------


def route_after_router(state: KestrelState) -> str:
    """Return the edge label for the conditional branch after router_node."""
    route = state.get("route", "retrieval")
    if route in ("chit_chat", "off_topic"):
        return "finalise"  # skip retrieval + synthesis + verification
    return "retrieve"


def route_after_verifier(state: KestrelState) -> str:
    """Return the edge label for the conditional branch after verifier_node."""
    verdict = state.get("verification_verdict", "supported")
    retries = state.get("retries", 0)
    
    if retries < 1:
        if verdict == "insufficient_evidence":
            return "retriever"
        for c in state.get("verified_claims", []):
            if c["verdict"] in ("insufficient_evidence", "partially_supported"):
                return "retriever"
                
    return "finaliser"


__all__ = [
    "router_node",
    "retriever_node",
    "synthesiser_node",
    "verifier_node",
    "finaliser_node",
    "route_after_router",
    "route_after_verifier",
]
