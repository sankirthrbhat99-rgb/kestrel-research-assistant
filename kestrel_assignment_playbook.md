# Kestrel Multi-Agent Research Assistant: Build Playbook

Deadline: Sep 20, 2026, 11 PM. Everything below is ordered so that a working, traceable, evaluated system exists early and polish comes last.

---

## 0. How to use this file

1. Do the **5-minute prep** (section 1).
2. Paste **Prompt 0** into your coding tool once. It becomes the standing context (save it as `AGENTS.md` / `GEMINI.md` / `CLAUDE.md` in the repo so every later session re-reads it).
3. Run Prompts 1 to 9 in order. After each, run the "Check" line yourself before moving on.
4. Do not skip Prompt 6 (baseline before improvement). The improvement section of the grade needs real before/after numbers.

## 1. 5-minute prep (do before any coding)

- Create the repo, copy `corpus.jsonl` in unchanged at the root. Expected SHA-256:
  `b401a4f906446f4e93f1d58c714918acf40d94d81a80c6358e5b7edd46cbbb41`
  (never open it in an editor that reformats line endings; `git add` it untouched).
- Get keys now: `GROQ_API_KEY` and/or `GEMINI_API_KEY` (runtime generation), `LANGSMITH_API_KEY` (create a project called `kestrel-research-assistant`).
- In LangSmith, invite `radialpulse@nxtwave.co.in` to the workspace/project now, so you do not forget at 10:55 PM.
- Python 3.11+ venv.

---

## 2. What the assignment actually requires (condensed)

| Area (weight) | What must exist |
|---|---|
| Multi-agent (25%) | 3+ agents (planner/router, retriever with a search tool, critic/verifier, synthesiser), explicit shared state, multi-turn memory ("how many of them can I create?"), local vector store (Chroma/FAISS/LanceDB), orchestration choice justified |
| RAG (25%) | Retrieve before answering; cite `chunk_id` + title; verifier verdict per claim (`supported`, `partially_supported`, `conflicting_evidence`, `insufficient_evidence`); say "not answered" plainly; on conflicts show both sides, say which is more reliable and why |
| Eval (20%) | 15+ original questions (single_hop, multi_hop, conflicting, unsupported, follow_up) in `results/eval_questions.jsonl`; retrieval, faithfulness, relevance, end-to-end correctness, plus one extra metric; one improvement driven by the numbers |
| LangSmith (15%) | Full traces (router to answer, each retrieval, each agent I/O), dataset run, feedback metrics, at least 3 traced runs incl. one unsupported and one multi-hop; latency and cost notes |
| Code (15%) | One command run, README, `.env.example`, no secrets, design doc with architecture diagram, reflection |

Hard rules that cost points if missed: local embeddings only (no hosted embedding API), Groq or Gemini for generation, sequential calls with 429 retry/backoff, corpus unchanged, eval questions in a separate file, exact file and field names in `results/`.

### What I saw in the corpus (154 chunks, 25 docs, about 129k characters, roughly 840 characters per chunk)

- The whole corpus is small enough (roughly 30k+ tokens) to fit in one long-context window. That is great for **writing eval questions** with a tool, but the system itself must still do real retrieval.
- **Dated conflicts are deliberate.** Example: the 4.1 release notes raise the KQL timeout from 30 to 60 seconds, so any document written earlier that says 30 seconds is stale. Publish dates vary a lot (`policy-security-compliance` is 2024-05, `eng-oncall-runbook` 2025-03, `spec-trails` and `eng-ingest-architecture` 2025-07, versus most specs at 2026-02). Your critic must compare `published`/`version` when sources disagree.
- **Multi-hop chains are built in:** incident post-mortem names the root cause and fixing release, the release notes date it, the pricing page says which plan gets the affected feature.
- **Chunks overlap** (the end of one chunk repeats at the start of the next), so top-k results often contain near-duplicates. De-duplicate or expand neighbours.
- Chunk IDs are `doc_id:n` and sequential, so neighbour expansion (`n-1`, `n+1`) is trivial.

### Recommended architecture (keep it simple enough to finish tonight)

- **Orchestration: LangGraph** (shared typed state, conditional edges, native LangSmith tracing, easy per-node status streaming to the UI).
- **Agents:**
  1. **Router/Planner**: rewrites follow-ups into standalone questions using chat history; classifies (needs retrieval / off-topic / chit-chat); decomposes multi-hop questions into sub-queries.
  2. **Retriever** (tool: `search_corpus`): hybrid retrieval, BM25 + dense embeddings, fused with reciprocal rank fusion; one call per sub-query; returns ranked chunks with metadata (title, published, version).
  3. **Verifier/Critic**: checks each claim in a draft against the retrieved chunks, emits verdict, flags stale vs newer sources by `published` date; can request one more retrieval round (bounded loop, max 1 retry).
  4. **Synthesiser**: writes the final answer with inline `[chunk_id]` citations, states uncertainty, presents both sides on conflict.
- **Embeddings:** `BAAI/bge-small-en-v1.5` or `sentence-transformers/all-MiniLM-L6-v2` (name it in the README). **Vector store:** Chroma (persistent dir, gitignored, rebuilt by the run command).
- **Generation:** Groq (a Llama 70B-class model) or Gemini Flash; check current model names and free-tier limits on the provider dashboards, since they change.
- **UI:** Streamlit with `st.status` per agent and a citations panel.

---

## 3. Which tool should you use?

**Short answer: use Antigravity Pro as your main builder, spend its quota deliberately, and use the DeepSeek tokens as the high-volume workhorse and fallback. Get Gemini CLI ready as a free third option.**

Reasoning:

- This job is *agentic*: multi-file scaffolding, installing packages, running the app, reading tracebacks, re-running evals, fixing. Tools that can run a terminal loop and look at results (an agentic IDE) save the most wall-clock time. Antigravity is built for that; it is the strongest fit for the parts where errors compound (LangGraph wiring, LangSmith tracing, the eval runner).
- The limit is the **weekly quota**. You have one deadline tonight, so a weekly quota is fine as long as you do not burn it on trivial prompts. Reserve it for Prompts 1, 2, 3, 5, 6 (the core system). Do not spend it on README/design doc/eval-question drafting.
- The DeepSeek route is best for **bulk, low-risk, easily verified work**: drafting eval questions (verified by a script), README, design doc, reflection, unit tests. Caveat: I do not know the specifics of your Token Harbor allocation or that harness (context limit, rate limits, how reliable its tool-calling/terminal use is). Run a 2-minute smoke test first: ask it to create a file, run a shell command, and read the output. If it fumbles that, use it only as a chat-style generator and paste results in yourself.
- **Important distinction:** the tool you *code with* is not the model your app *runs on*. Your shipped system must call Groq or Gemini (free tier, documented), not DeepSeek.

**Other options worth having on standby:**

| Tool | Why it could help |
|---|---|
| **Gemini CLI** (Google login) | Free tier, terminal agent, very large context, so it can read the entire corpus at once. Good fallback if Antigravity quota runs out. |
| **Claude Code / Cursor / Codex CLI** (if you already have access) | Strong at multi-file refactors and test-fix loops. Only use if you already have credits; do not sign up for something new tonight. |
| **Aider + DeepSeek API** | A lightweight, git-aware way to use your DeepSeek tokens if the Token Harbor harness is awkward. |

Quotas and pricing move quickly, so check each dashboard rather than trusting a table.

**Suggested split:**

| Task | Tool |
|---|---|
| Prompt 0 to 3 (scaffold, retrieval, agents, tracing) | Antigravity |
| Prompt 4 (eval questions) | DeepSeek or Gemini CLI (needs whole corpus), then verify with script |
| Prompt 5 to 6 (eval runner, baseline, improvement) | Antigravity |
| Prompt 7 (UI) | DeepSeek |
| Prompt 8 to 9 (docs, final QA) | DeepSeek, then Antigravity for the final QA |

---

## 4. Suggested timeline (compress to fit the hours you have left)

| Block | Work | Done when |
|---|---|---|
| 1 | Prep + Prompts 0 to 1 | `python -m kestrel.ingest` builds the index; a search returns sensible chunks |
| 2 | Prompts 2 to 3 | One question runs through all agents; trace visible in LangSmith |
| 3 | Prompt 4 in parallel | 20 verified questions in `results/eval_questions.jsonl` |
| 4 | Prompts 5 to 6 | **Baseline** results saved, then one improvement, then re-run |
| 5 | Prompts 7 to 8 | UI works; README, design doc, reflection written |
| 6 | Prompt 9 | Clean-clone test passes; LangSmith access shared; repo link submitted |

**Freeze feature work about 60 minutes before the deadline.** Submit at least 15 minutes early.

---

## 5. Prompts

### Prompt 0: Standing context (paste once, also save as AGENTS.md)

```
You are helping me finish a take-home assignment: a multi-agent research assistant over a fictional company's internal docs (Kestrel Labs, a product-analytics SaaS). Deadline is tonight, so favour simple, working, well-traced code over clever code. Do not add features I did not ask for.

FIXED CONSTRAINTS
- Data: corpus.jsonl at repo root (154 chunks, 25 docs). Fields: chunk_id, doc_id, title, category, owner, source_url, published (YYYYMMDD), version, text. It is READ-ONLY: never modify, reformat or re-save it. Expected sha256: b401a4f906446f4e93f1d58c714918acf40d94d81a80c6358e5b7edd46cbbb41
- Orchestration: LangGraph. At least 4 agents: router/planner, retriever (with a search tool), verifier/critic, synthesiser. Shared typed state so later agents see earlier decisions and retrieved evidence. Multi-turn conversations must work (follow-ups like "how many of them can I create?" resolve against the previous turn).
- Vector store: Chroma (local, persistent, gitignored). Embeddings: LOCAL sentence-transformers model only (BAAI/bge-small-en-v1.5). No hosted embedding APIs.
- Generation: Groq or Gemini free tier, selectable via env var (LLM_PROVIDER, LLM_MODEL). Calls must be sequential, output length capped, HTTP 429 handled with bounded retry and exponential backoff.
- Keys only from environment (GROQ_API_KEY, GEMINI_API_KEY, LANGSMITH_API_KEY, LANGSMITH_PROJECT, LANGSMITH_TRACING). Provide .env.example. Never commit secrets. .env must be gitignored.
- Every final answer cites chunk_id and title. The verifier records a verdict per material claim: supported | partially_supported | conflicting_evidence | insufficient_evidence.
- If evidence is missing, the answer must say so plainly. If sources disagree, present both, say which is more reliable (usually the newer `published` date / higher version) and why.
- Whole system runs end to end with ONE command after env vars are set.
- Whole workflow is traced in LangSmith (every agent, every retrieval).

OUTPUT FILES (exact names and fields, they are machine-compared)
- results/eval_questions.jsonl: question_id, question, type (single_hop|multi_hop|conflicting|unsupported|follow_up), conversation_id and turn (for follow-ups), expected_answer (null for unsupported), expected_chunk_ids
- results/eval_results.jsonl: one line per question: question_id, answer, citations (list of chunk_ids cited), retrieved_chunk_ids (ranked list), verifier_verdict, scores (object keyed by metric name), latency_seconds, langsmith_run_url
- results/metrics_summary.json: aggregate per metric, breakdown by question type, total token usage, total wall-clock time, generation and embedding models used
- results/improvement.md: what was observed, what was changed, metric values before and after

WORKING STYLE
- Work in small steps. After each step, run the code and show me the actual output. Do not claim something works unless you ran it.
- Never invent metric numbers. All numbers in results/ must come from real runs.
- Ask me only if truly blocked; otherwise choose the simplest reasonable option and tell me what you chose.
Reply "ready" and wait for Prompt 1.
```

**Check:** it says "ready" and creates the memory file. Nothing else yet.

---

### Prompt 1: Scaffold, ingestion, hybrid retrieval

```
Step 1: project scaffold and retrieval layer. Do NOT build agents yet.

1. Create this layout:
   kestrel/ (package): config.py, llm.py, ingest.py, retrieval.py
   results/, tests/, requirements.txt, .env.example, .gitignore (ignore .env, .chroma/, __pycache__/, .venv/)
2. config.py: load env vars, model names, constants (TOP_K, RRF constant, chunk paths). Use python-dotenv.
3. llm.py: one function `generate(messages, max_tokens, temperature=0)` that supports Groq and Gemini via LLM_PROVIDER. Sequential calls only. On HTTP 429 or transient errors: bounded retry (max 5) with exponential backoff plus jitter, honour Retry-After if present. Track cumulative prompt/completion token usage in a module-level counter that other code can read. Cap max_tokens.
4. ingest.py: read corpus.jsonl (never write to it), embed each chunk text with the local model (prefix titles into the embedded text: "{title}\n{text}"), store in a persistent Chroma collection with metadata (chunk_id, doc_id, title, category, published, version). Also build a BM25 index (rank_bm25) over the same text. Idempotent: skip if index already matches the corpus hash. Print the corpus sha256 and warn if it differs from b401a4f906446f4e93f1d58c714918acf40d94d81a80c6358e5b7edd46cbbb41.
5. retrieval.py: `search_corpus(query, k=6)` returning a ranked list of dicts {chunk_id, title, published, version, text, score}. Implement it as a SWITCHABLE strategy via config: "dense" (vector only) and "hybrid" (BM25 + dense fused with reciprocal rank fusion). Default = "dense" for now, because I need a genuine baseline later. Add optional neighbour expansion (include chunk n-1 / n+1 of the same doc) controlled by a flag, default off. De-duplicate overlapping text when returning results.
6. tests/test_retrieval.py: 3 smoke tests using real corpus queries (e.g. Beacon limits per plan, KQL query timeout, Redshift availability) asserting that a plausible doc_id appears in the top 6.

Run ingest, run the tests, and show me the top-6 results (chunk_id + title only) for the query "What is the KQL query timeout?". Then stop.
```

**Check:** tests pass; the KQL query shows chunks from more than one document (that is the conflict you need to handle).

---

### Prompt 2: The four agents and the LangGraph workflow

```
Step 2: build the multi-agent LangGraph workflow in kestrel/agents.py and kestrel/graph.py.

SHARED STATE (TypedDict): chat_history, question, standalone_question, route (retrieve|off_topic), sub_queries, retrieved (list of chunk dicts, with the retriever's ranked chunk_id list preserved), draft_answer, claims (list of {claim, chunk_ids, verdict, note}), verifier_verdict (overall), retries, final_answer, citations, agent_log (list of {agent, input_summary, output_summary, seconds}).

AGENTS (each is a graph node; each has its own prompt in kestrel/prompts.py):
1. router_planner: (a) rewrite follow-ups into a standalone question using chat_history (resolve pronouns like "them", "it", "that plan"); (b) decide if the question is about Kestrel (must retrieve) or off-topic/chit-chat; (c) decompose multi-hop questions into 1 to 3 sub_queries (e.g. incident -> fixing release -> plan availability). Output strict JSON.
2. retriever (TOOL: search_corpus): run each sub_query through search_corpus sequentially, merge and de-duplicate, keep ranked order, keep published/version metadata. No LLM call needed unless useful.
3. synthesiser (draft): write a concise answer using ONLY the retrieved chunks. Every factual sentence ends with [chunk_id]. If the chunks do not answer the question, say plainly that the documents do not contain it. Include the document's published date when relying on it.
4. verifier_critic: split the draft into material claims; for each, check against the cited chunk text and record verdict supported | partially_supported | conflicting_evidence | insufficient_evidence. It must explicitly compare `published`/`version` when two retrieved chunks disagree on the same fact, and name the more reliable one and why. Output strict JSON. If overall verdict is insufficient_evidence or a claim is unsupported AND retries < 1, route back to the retriever ONCE with a refined query; otherwise continue.
5. finalizer: produce final_answer with citations (chunk_id + title), remove claims marked insufficient_evidence or restate them as "not found in the documents", and for conflicting_evidence present both sources, the newer one flagged as more reliable with the reason.

CONDITIONAL EDGES: off_topic -> finalizer directly (short polite refusal, no retrieval, but still traced). verifier -> retriever (max 1 retry) or -> finalizer.

ROBUSTNESS: LLM JSON parsing with one repair attempt and a safe fallback; never crash the graph on a bad model output. Keep max_tokens small per agent (router 200, synthesiser 400, verifier 500).

INTERFACE: `run_question(question, chat_history) -> dict` and a streaming variant `stream_question(...)` that yields (agent_name, status, payload) events for the UI.

Add a CLI: `python -m kestrel.chat` for a multi-turn terminal chat. Test with these 4 turns and show me the full output, including verifier verdicts:
 (1) "How many Beacons can I create on the Growth plan?"
 (2) "And on Scale?"
 (3) "What is the KQL query timeout?"
 (4) "What is the CEO's favourite colour?"
```

**Check:** turn 2 resolves to Scale Beacons (500 per project), turn 4 says the documents do not contain it, turn 3 shows the 30s vs 60s handling.

---

### Prompt 3: LangSmith tracing

```
Step 3: LangSmith observability.

1. Enable tracing through env vars (LANGSMITH_TRACING=true, LANGSMITH_API_KEY, LANGSMITH_PROJECT=kestrel-research-assistant). Confirm every node in the graph appears as a child run under one root run per question.
2. Decorate `search_corpus` with @traceable(run_type="retriever") so each retrieval shows its query and returned chunk_ids. Decorate LLM calls so token usage and model name show on each run. Tag runs with the agent name and a conversation_id in metadata.
3. Add a helper `get_run_url(run)` that returns the shareable LangSmith URL of the ROOT run for a question (use RunTree / the langsmith Client; verify it actually returns a working URL, do not guess the API). The eval script will need this for `langsmith_run_url`.
4. Run 3 representative questions and print each root run URL: one single-hop, one multi-hop (incident -> release -> plan), one unsupported. Confirm in the LangSmith UI structure that router, retriever (with each retrieval), synthesiser, verifier and finalizer all show their inputs and outputs. Tell me if anything is missing.
```

**Check:** open the three URLs yourself. If a reviewer cannot follow router to answer, fix it now.

---

### Prompt 4: Evaluation questions (use a big-context tool; verify by script)

```
I need the evaluation set for a RAG assignment. Below is the entire corpus (corpus.jsonl). READ ALL OF IT FIRST. Then write 20 ORIGINAL questions that a reviewer would consider hard and fair.

Output file: results/eval_questions.jsonl, one JSON object per line with exactly these fields: question_id (q01..q20), question, type, conversation_id and turn (ONLY for follow_up rows, otherwise omit or null), expected_answer (null for unsupported), expected_chunk_ids (list of real chunk_id values).

Mix (total 20):
- 5 single_hop (one fact in one chunk: limits, defaults, plan inclusions)
- 5 multi_hop (needs 2+ documents, e.g. post-mortem -> fixing release -> which plan gets the feature; pricing + release-note combos)
- 3 conflicting (two documents disagree because one is stale; the correct answer uses the newer `published` date. Look for values that changed between versions, and for older-published docs such as spec-trails, eng-ingest-architecture, eng-oncall-runbook, policy-security-compliance that may not match newer release notes/pricing)
- 3 unsupported (plausible Kestrel questions the corpus does NOT answer; expected_answer = null; expected_chunk_ids = [])
- 4 follow_up: two conversations with 2 turns each (same conversation_id, turn 1 and 2). The turn-2 question must use a pronoun or ellipsis ("how many of them...", "and on Scale?") and depend on turn 1.

Rules:
- Every expected_answer must be verifiable from the listed chunks. For conflicting questions, expected_answer must state the correct (newer) value and mention the stale one.
- expected_chunk_ids must include ALL chunks needed (both sides for conflicts).
- Vary wording; do not copy sentences from the corpus into questions.
- Do not invent facts. If unsure, drop the question and write another.

Then WRITE and RUN a validation script tests/validate_eval_questions.py that checks: valid JSON per line, required fields present, type values valid, every expected_chunk_id exists in corpus.jsonl, unsupported rows have null answer and empty chunk list, follow_up rows have conversation_id and turn, counts per type match the mix above. Show me the script output. List any question you are less than 90% sure about so I can double check it by hand.

[PASTE corpus.jsonl CONTENTS HERE, or attach the file if the tool supports it]
```

**Check:** spot-check at least 5 questions by hand against the source chunks, especially every conflicting one. A wrong gold answer will make your own system look bad.

---

### Prompt 5: Evaluation runner, metrics, LangSmith dataset

```
Step 5: evaluation harness in eval/run_eval.py. It reads results/eval_questions.jsonl (never modifies it) and the running graph.

1. Create/update a LangSmith DATASET from the questions (inputs: question, conversation_id, turn, prior turns; reference outputs: expected_answer, expected_chunk_ids, type). Run the evaluation as a LangSmith experiment via langsmith.evaluate (or client-based equivalent) so results appear as a dataset run. Run questions SEQUENTIALLY (max_concurrency=1). For follow_up questions, replay the earlier turn(s) of the same conversation first so history is real.
2. Metrics (each attached to the run as LangSmith feedback AND stored in scores):
   - retrieval_recall@k: fraction of expected_chunk_ids present in retrieved_chunk_ids (for unsupported questions, skip or score 1 if nothing relevant is claimed)
   - retrieval_mrr: reciprocal rank of the first expected chunk
   - faithfulness: LLM-judge (or verifier-derived) share of answer claims supported by the retrieved chunks
   - answer_relevance: LLM-judge 0..1, does the answer address the question
   - correctness (end-to-end): LLM-judge comparing to expected_answer, BUT set to 0 if the answer's cited chunks do not include at least one expected chunk (assignment says correct answers not backed by cited chunks do not count). For unsupported questions, correct = the answer clearly says the documents do not settle it.
   - citation_precision (extra metric): share of cited chunk_ids that are in expected_chunk_ids or were actually retrieved and relevant.
   Judge prompts: temperature 0, strict JSON, short outputs, sequential calls with the shared retry/backoff.
3. Write results/eval_results.jsonl (exact fields: question_id, answer, citations, retrieved_chunk_ids, verifier_verdict, scores, latency_seconds, langsmith_run_url) and results/metrics_summary.json (aggregate per metric, breakdown by question type, total token usage, total wall-clock time, generation model, embedding model).
4. Accept a CLI flag --tag (e.g. baseline, improved) and --out-dir so I can keep baseline results separate (results/baseline/ copy) without overwriting them.
5. Run it. Show the aggregate table and per-type breakdown. Report how many free-tier 429 retries occurred.
```

**Check:** every line in `eval_results.jsonl` has a working LangSmith URL and all seven fields. The dataset run is visible in LangSmith.

---

### Prompt 6: Baseline, diagnose, ONE improvement, re-run

```
Step 6: the required "evaluation-driven improvement".

1. Ensure the current config is the BASELINE (dense retrieval, no neighbour expansion, current prompts). Run the eval with --tag baseline and copy the outputs to results/baseline/ (keep them; they are evidence).
2. Analyse the failures: list the 5 lowest-scoring questions, and for each say from the actual data/traces whether the failure was retrieval (expected chunk not in retrieved list), verifier (missed a stale-source conflict), synthesis (wrong or uncited claim), or judge noise. Show the evidence (chunk ids, verdicts).
3. Choose the SINGLE most impactful, best-evidenced change. Candidates depending on what the data shows: (a) switch retrieval from dense to hybrid BM25+dense (RRF); (b) enable neighbour-chunk expansion; (c) make the verifier explicitly compare published dates and force the synthesiser to present both sides on conflict; (d) multi-query decomposition for multi-hop. Do not pick something the data does not justify.
4. Implement it, re-run the eval with --tag improved.
5. Write results/improvement.md with: what I observed (with metric values and 1 or 2 example question_ids and LangSmith trace URLs), what changed (files/config), before-vs-after table for every metric and by question type, and an honest note on any metric that got worse or on noise (small test set).
Never fabricate numbers; every figure must come from the two runs. If the change did not help, say so and try the next best candidate, keeping both attempts documented.
```

**Check:** the before/after table matches the files in `results/`. Honest "it helped here, it hurt there" is better than a perfect-looking story.

---

### Prompt 7: Streamlit UI

```
Step 7: minimal Streamlit UI in app.py (visual polish not needed).
- Multi-turn chat using st.session_state; a "New conversation" button.
- While a question runs, show the status of each agent live (router -> retriever -> synthesiser -> verifier -> finalizer) using the streaming events from stream_question, with a one-line summary of each agent's output (e.g. the rewritten question, the sub-queries, number of chunks retrieved, verdict).
- Show the final answer, then a Citations panel listing chunk_id, title, published date and an expander with the cited chunk text, plus the verifier verdict per claim (colour-coded).
- Show a link to the LangSmith root run for that question if available.
- Handle errors gracefully (rate limit exhausted -> friendly message, not a stack trace).
Run it headless once to make sure it starts without errors, and tell me the exact command to launch it.
```

---

### Prompt 8: Documentation (README, design doc, reflection)

```
Step 8: documentation. Keep everything concise and factual, based on the real code and real results in this repo. Do not invent numbers or claims.

1. README.md: what it is; requirements; setup (venv, pip install -r requirements.txt, cp .env.example .env); env vars table; the ONE-COMMAND run (create a Makefile target or run.sh that does: ingest if needed -> run eval -> write results/ ; and a separate command for the Streamlit UI); embedding model name and generation model/provider named explicitly; repo layout; how to view LangSmith traces; note that the corpus is unchanged with its sha256.
2. docs/design.md: one-page architecture. Include a Mermaid diagram of the agents and hand-offs (router/planner -> retriever(tool) -> synthesiser -> verifier -> [retry once] -> finalizer, with the off-topic shortcut), the shared state fields passed between agents, and 4 to 6 sentences each on: orchestration choice (why LangGraph), retrieval design (hybrid/dense, neighbour expansion, dedup), how conflicts and stale documents are handled (published date comparison), how unsupported questions are handled, free-tier handling (sequential calls, capped outputs, 429 backoff).
3. docs/reflection.md: trade-offs, cost and latency observations (use real numbers from results/metrics_summary.json and LangSmith), what worked, what didn't, what I would do next (3 to 5 concrete items).
4. Verify README commands by actually running them in a fresh venv and report any that fail.
```

---

### Prompt 9: Final QA before submitting (run ~30 to 45 minutes before deadline)

```
Final QA. Act as the reviewer and check every item, reporting PASS/FAIL with evidence. Fix FAILs, then re-check.

1. `sha256sum corpus.jsonl` equals b401a4f906446f4e93f1d58c714918acf40d94d81a80c6358e5b7edd46cbbb41 and git shows the file unmodified from the original.
2. No secrets in the repo or git history: grep for key patterns (gsk_, AIza, lsv2_, sk-) in working tree AND `git log -p`. .env is gitignored; .env.example has placeholders only.
3. Clean-clone test: clone into a temp dir, create a fresh venv, follow ONLY the README, run the one command. It must finish without manual intervention.
4. results/ has all four files with exact names; validate with a script: every eval_results line has question_id, answer, citations, retrieved_chunk_ids, verifier_verdict, scores, latency_seconds, langsmith_run_url; citations are chunk_ids that exist in corpus.jsonl; eval_questions.jsonl has 15+ rows covering all 5 types with valid fields; metrics_summary.json has aggregate metrics, per-type breakdown, token usage, wall-clock time, and both model names; improvement.md has before/after numbers that match results/baseline vs the final results.
5. A held-out-style test: ask the system 5 NEW questions not in the eval set (one unsupported, one conflicting, one multi-hop, one follow-up) and show answers with citations and verdicts.
6. The three required traces exist in LangSmith (one unsupported, one multi-hop, one other) and the URLs in eval_results.jsonl open.
7. README, docs/design.md (with diagram), docs/reflection.md all present.
List remaining risks, ranked.
```

---

## 6. Manual checklist (things no tool can do for you)

- [ ] LangSmith project shared with `radialpulse@nxtwave.co.in`
- [ ] Repo link is accessible to reviewers (public, or the reviewer is invited)
- [ ] Open 3 LangSmith trace URLs in an incognito window / as the reviewer would
- [ ] `.env` not committed; keys revoked/rotated after grading if you pasted them anywhere
- [ ] Submitted before 11 PM with a buffer

## 7. Free-tier survival tips

- Groq free limits are usually tighter on tokens per minute than requests; keep prompts short (top-6 chunks, not 20) and outputs capped.
- If one provider rate-limits you mid-eval, switch `LLM_PROVIDER` for the *remaining* run only if you record it, since `metrics_summary.json` must name the models actually used. Simpler: pick one and run the eval once cleanly.
- Cache nothing that hides real latency from your reported numbers, but do cache the embeddings/index so re-runs are quick.
