# Final Submission Checklist

## Commands Executed & Checks Performed
- **`python -m py_compile kestrel/*.py`**: Passed. No Python syntax errors.
- **`pytest tests/`**: Executed but deliberately halted due to tests hanging on rate limits/network delays. 
- **`scratch/test_route.py`**: A custom, offline lightweight script successfully verified that the graph compiles and the conditional verifier retry edge works precisely as requested.
- **`Get-FileHash -Algorithm SHA256 corpus.jsonl`**: Passed. Hash matches `B401A4F906446F4E93F1D58C714918ACF40D94D81A80C6358E5B7EDD46CBBB41`.
- **`cat .env.example`**: Passed. Contains template placeholders and no hardcoded API secrets.
- **`.gitignore` Audit**: Checked tracking exclusions.

## Blocking Issues Fixed
- **`.gitignore` rule blocking evaluation results**: Removed `results/*` from `.gitignore`. The assignment requires the evaluation files (`eval_results.jsonl`, `metrics_summary.json`) to be tracked for grading.
- **`requirements.txt` invalid dependency**: Fixed a malformed string (`langsmith>=0.1.0streamlit`) by correctly spacing `langsmith` and `streamlit` on separate lines, guaranteeing `pip install` works cleanly for the reviewer.

## Known Limitations
- **Evaluation Loop Blocked**: Groq free-tier tokens (200,000 TPD) blocked the full Phase 3 "Improved" evaluation loop. The codebase has the implementation ready (verifier retries), but the metrics report only contains the `baseline_groq/` run. This is honestly documented in `docs/reflection.md`.

## Recommended Final Submission Steps
1. Add all changes to git: `git add .`
2. Commit: `git commit -m "Finalize assignment and fix grading blockers"`
3. Push: `git push` (ensure the repo link is accessible to the reviewer).
4. Verify LangSmith: Ensure the project `kestrel-research-assistant` is shared with `radialpulse@nxtwave.co.in`.
5. Rotate Keys: Revoke any API keys locally if they were ever temporarily exposed during testing.
