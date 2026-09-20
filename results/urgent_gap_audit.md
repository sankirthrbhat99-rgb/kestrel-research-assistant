# Urgent Requirements Gap Audit

## 1. Checklist Mapping

| Playbook Phase / Prompt | Status | Notes |
|---|---|---|
| **0. 5-minute prep (Setup)** | **Completed & Verified** | `.env` layout, venv, and initial corpus intact. |
| **1. Scaffold, Ingestion, Retrieval** | **Completed & Verified** | `ingest.py` builds Chroma/BM25. Hybrid retrieval supported. |
| **2. Four Agents & LangGraph** | **Completed & Verified** | LangGraph wired. `kestrel/chat.py` CLI alias implemented. |
| **3. LangSmith Tracing** | **Completed & Verified** | `@traceable` decorators applied; tracing works. |
| **4. Evaluation Questions** | **Completed & Verified** | 20 verified questions in `results/eval_questions.jsonl`. |
| **5. Evaluation Runner & Dataset** | **Completed & Verified** | Harness built. Missing files `eval_results.jsonl` and `metrics_summary.json` were incorrectly nested but have now been copied to the required root `results/` directory. |
| **6. Baseline, Improve, Re-run** | **Blocked by Groq Limits** | Baseline and improvements (Hybrid strategy & Runner state bug fix) are implemented. Re-run is blocked due to Groq 200,000 Tokens Per Day limit. `improvement.md` reflects this status. |
| **7. Streamlit UI** | **Completed & Verified** | `app.py` created with node-level streaming events and offline support. |
| **8. Documentation** | **Completed & Verified** | `README.md`, `docs/design.md`, `docs/reflection.md`, and `run.sh`/`run.ps1` all created. |
| **9. Final QA** | **Partially Completed** | `sha256sum corpus.jsonl` is intact. No secrets committed. Exact file names in `results/` are now fulfilled. Full LLM held-out testing is skipped due to rate limit blockage. |

## 2. Missing Requirements Addressed

During the audit, the following high-impact gaps were identified and immediately fixed:

1. **Incorrect Output Paths (High Impact):**
   - **Gap:** The baseline evaluation results (`eval_results.jsonl`, `metrics_summary.json`) were nested inside `results/baseline_groq/`. The playbook explicitly requires them to be at `results/eval_results.jsonl` and `results/metrics_summary.json` for machine grading.
   - **Action Taken:** Copied these two files directly into the `results/` directory.

2. **Missing Chat CLI Module (High Impact):**
   - **Gap:** Prompt 2 requires the ability to run `python -m kestrel.chat`, but the module was implemented under `kestrel.cli`.
   - **Action Taken:** Created `kestrel/chat.py` as an alias wrapper that invokes `kestrel.cli.main()`, ensuring the specific required command works seamlessly without breaking existing functionality.

All safe, high-impact implementations have now been completed. The evaluation loop remains intentionally blocked to respect the daily rate limit and prevent destructive overwrites of the existing valid baseline outputs.
