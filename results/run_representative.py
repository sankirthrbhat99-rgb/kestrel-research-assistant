"""Representative run script for the Kestrel Multi-Agent Research Assistant.

Runs three test cases and writes results to results/representative_runs.md.

Usage::

    python results/run_representative.py

The script detects whether a real LLM is configured and labels every answer
accordingly (OFFLINE or the provider name).  Trace URLs are included when
LangSmith is configured; otherwise they are reported as None with a note.
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load .env if present.
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
except ImportError:
    pass

from kestrel.graph import build_graph, run_query_traced
from kestrel.llm import LLMConfig
from kestrel.tracing import is_tracing_enabled


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

CASES = [
    {
        "label": "Single-hop",
        "description": "A straightforward factual lookup from a single document.",
        "question": "How many Beacons can I create on the Growth plan?",
        "history": [],
    },
    {
        "label": "Multi-hop (follow-up with pronoun resolution)",
        "description": (
            "A follow-up question that requires resolving 'And on Scale?' "
            "using the previous answer about Growth plan Beacons."
        ),
        "question": "And on Scale?",
        "history": [
            {"role": "user", "content": "How many Beacons can I create on the Growth plan?"},
        ],
        # history assistant content filled in after case 0 runs.
    },
    {
        "label": "Unsupported question",
        "description": (
            "A question that has no answer in the Kestrel knowledge base."
        ),
        "question": "What is the current stock price of NVIDIA?",
        "history": [],
    },
]


def _md_block(title: str, content: str) -> str:
    return f"```\n{content.strip()}\n```"


def run_all() -> str:
    cfg = LLMConfig.from_env()
    llm_mode = "OFFLINE (no API key configured)" if not cfg.configured else f"LIVE — provider: {cfg.provider}, model: {cfg.model}"
    tracing_mode = "ENABLED" if is_tracing_enabled() else "DISABLED (set LANGCHAIN_TRACING_V2=true + LANGCHAIN_API_KEY)"

    graph = build_graph()
    session_id = str(uuid.uuid4())

    lines: list[str] = [
        "# Kestrel Representative Runs",
        "",
        f"**Generated:** {time.strftime('%Y-%m-%dT%H:%M:%S')}  ",
        f"**LLM mode:** {llm_mode}  ",
        f"**LangSmith tracing:** {tracing_mode}  ",
        f"**Session ID:** `{session_id}`  ",
        "",
        "> Note: Without an API key all answers use the deterministic offline fallback",
        "> (keyword routing + chunk excerpt). Answers are prefixed `[OFFLINE]`.",
        "> With a real key the LLM produces fluent, cited answers.",
        "",
        "---",
        "",
    ]

    accumulated_history: list[dict[str, str]] = []

    for i, case in enumerate(CASES):
        label = case["label"]
        question = case["question"]
        history = case.get("history", [])

        # For case 1 (follow-up), use the actual accumulated history.
        if i == 1:
            history = list(accumulated_history)

        print(f"\n[{i+1}/3] Running: {label!r} — {question!r}")

        t0 = time.perf_counter()
        state, trace_url = run_query_traced(
            question,
            history=history,
            graph=graph,
            conversation_id=session_id,
        )
        elapsed = time.perf_counter() - t0

        # Accumulate history from the first turn for use in follow-ups.
        if i == 0:
            accumulated_history = [
                {"role": "user", "content": question},
                {"role": "assistant", "content": state.get("final_answer", "")},
            ]

        route = state.get("route", "—")
        verdict = state.get("verification_verdict", "—")
        answer = state.get("final_answer", "(no answer)")
        evidence_count = len(state.get("evidence", []))
        citations = state.get("citations", [])
        standalone = state.get("standalone_question", question)

        lines += [
            f"## Case {i+1}: {label}",
            "",
            f"**Question:** {question}  ",
            f"**Standalone rewrite:** {standalone}  ",
            f"**Route:** `{route}`  ",
            f"**Verification verdict:** `{verdict}`  ",
            f"**Evidence chunks retrieved:** {evidence_count}  ",
            f"**Elapsed:** {elapsed:.2f}s  ",
            f"**Trace URL:** {trace_url if trace_url else 'None (LangSmith not configured)'}  ",
            "",
            "### Answer",
            "",
            _md_block("Answer", answer),
            "",
        ]

        if citations:
            lines.append("### Citations")
            lines.append("")
            for c in citations:
                lines.append(f"- `{c.get('chunk_id', '?')}` — {c.get('title', '?')}")
            lines.append("")

        if evidence_count > 0:
            lines.append("### Top evidence chunks")
            lines.append("")
            for e in state["evidence"][:3]:
                snippet = e["text"][:200].replace("\n", " ").strip()
                lines.append(f"- `{e['chunk_id']}` (score={e['score']:.4f}): {snippet}…")
            lines.append("")

        if i == 1 and history:
            lines += [
                "### History used",
                "",
                f"- user: {history[0]['content'][:80]}…" if len(history) > 0 else "",
                "",
            ]

        lines.append("---")
        lines.append("")

        print(f"   route={route}  verdict={verdict}  evidence={evidence_count}  elapsed={elapsed:.2f}s")
        print(f"   trace_url={trace_url}")

    # Limitation note when offline.
    if not cfg.configured:
        lines += [
            "## Limitation Note",
            "",
            "All three runs above used the **deterministic offline fallback** because",
            "no LLM API key was found in the environment or `.env` file.",
            "",
            "To run with a real LLM:",
            "1. Copy `.env.example` to `.env`",
            "2. Set one of: `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`,",
            "   or `KESTREL_LLM_API_KEY`",
            "3. Re-run this script",
            "",
            "To enable LangSmith tracing additionally set:",
            "- `LANGCHAIN_TRACING_V2=true`",
            "- `LANGCHAIN_API_KEY=<your key from smith.langchain.com>`",
            "- `LANGCHAIN_PROJECT=kestrel-research-assistant`",
            "",
        ]

    if not is_tracing_enabled():
        lines += [
            "## LangSmith Status",
            "",
            "LangSmith tracing was **not active** during these runs.",
            "All `Trace URL` fields are `None`.",
            "",
            "When tracing is enabled, each run produces a URL like:",
            "`https://smith.langchain.com/projects/kestrel-research-assistant/runs/<run_id>`",
            "",
            "The URL is obtained by querying the LangSmith API after the graph completes —",
            "it is never fabricated by string interpolation.",
            "",
        ]

    return "\n".join(lines)


def main() -> int:
    print("=" * 60)
    print("  Kestrel Representative Runs")
    print("=" * 60)

    content = run_all()

    out_path = ROOT / "results" / "representative_runs.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    print(f"\nWritten to: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
