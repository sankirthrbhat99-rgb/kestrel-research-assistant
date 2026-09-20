$ErrorActionPreference = "Stop"

Write-Host "Running ingestion (if needed)..."
python -m kestrel.ingest

Write-Host "Starting evaluation run..."
python eval/run_eval.py --tag baseline --out-dir results/baseline

Write-Host "Evaluation complete."
