#!/usr/bin/env bash
set -euo pipefail

# Ensure this repo is importable (project root + src)
export PYTHONPATH="${PYTHONPATH:-}:$(pwd):$(pwd)/src"

# Run pytest for the new project only and collect results
pytest -q oswe-mini-m22a5s330/tests --maxfail=1

# Simple metrics collection (counts)
python - <<'PY'
import json,sys,glob
res={}
# find results_post.json files
for p in glob.glob('**/results_post.json', recursive=True):
    with open(p) as f:
        d=json.load(f)
        res[p]=d
with open('results/aggregated_metrics.json','w') as f:
    json.dump(res,f,indent=2)
print('Wrote results/aggregated_metrics.json')
PY
