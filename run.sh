#!/usr/bin/env bash
set -e

echo "Running ingestion (if needed)..."
python -m kestrel.ingest

echo "Starting evaluation run..."
python eval/run_eval.py --tag baseline --out-dir results/baseline

echo "Evaluation complete."
