#!/usr/bin/env bash
set -euo pipefail
# Run pytest and print a short summary and location of artifacts
pytest -q tests || true

echo
echo "Artifacts:"
echo "  logs/log_post.txt"
echo "  results/results_post.json"
echo "  compare_report.md"
