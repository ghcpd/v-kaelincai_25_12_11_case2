#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="${PYTHONPATH:-}:$(pwd):$(pwd)/src"
pytest -q oswe-mini-m22a5s330/tests --maxfail=1
python ./oswe-mini-m22a5s330/scripts/aggregate_results.py
echo "Artifacts written to oswe-mini-m22a5s330/results/aggregated_metrics.json"