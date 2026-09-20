# Retrieval Evaluation Comparison

This report strictly measures retrieval quality (Dense vs. Hybrid) using local indexes, circumventing the LLM rate limits.

## Overall Metrics (Top-5)

| Strategy | MRR | Recall@5 |
|----------|-----|----------|
| Baseline (Dense) | 0.585 | 0.526 |
| Improved (Hybrid) | 0.679 | 0.690 |

## Breakdown by Question Type

| Type | Baseline MRR | Improved MRR | Baseline Recall | Improved Recall |
|------|--------------|--------------|-----------------|-----------------|
| single_hop | 0.440 | 0.667 | 0.800 | 1.000 |
| multi_hop | 0.900 | 1.000 | 0.420 | 0.610 |
| conflicting | 1.000 | 1.000 | 0.806 | 0.917 |
| unsupported | 0.000 | 0.000 | 0.000 | 0.000 |
| follow_up | 0.500 | 0.562 | 0.500 | 0.750 |
