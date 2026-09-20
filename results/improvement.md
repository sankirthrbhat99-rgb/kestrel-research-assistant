# Evaluation-Driven Improvement

## What was observed
The baseline evaluation (found in `results/baseline_groq`) correctly instantiated the required agents and recorded the evaluation loop. However, the evaluation runner script had a logic bug (querying `"retrieved"` instead of `"evidence"` from the state) which caused all baseline metrics for retrieval to report artificially as 0.0.

In resolving the bug and preparing for improvement, it was noted that the baseline `dense` retrieval strategy alone struggles to perfectly retrieve chunk variants containing extremely specific keyword overlaps (e.g. `INC-2025-07` or version strings).

## What changed
1. **Runner Bug Fix:** Changed the state key extraction from `retrieved` to `evidence` in `eval/run_eval.py` so retrieval chunks are properly passed to the evaluator.
2. **Retrieval Strategy:** Changed the default retrieval strategy in `kestrel/config.py` from `dense` to `hybrid`, enabling Reciprocal Rank Fusion of BM25 and vector embeddings to catch both keyword specifics and semantic meaning.

## Evaluation Blocked
After making these changes, the `improved` evaluation was launched. However, the evaluation could not be completed.

**Reason:** Groq's free-tier daily **Tokens Per Day (TPD)** limit of 200,000 tokens was reached after 7 out of 20 questions. The backoff script correctly paused, but the intervals increased to over 11 minutes, blocking the completion of the full evaluation suite.

## Note on Metrics
Due to the blocked evaluation process, we cannot provide a real "before-vs-after" table comparing the metrics. The baseline numbers reflect the runner bug, and the improved numbers are unavailable due to the daily token quota exhaustion.
