#!/usr/bin/env bash

# Run pytest and produce JSON results
pytest -q --disable-warnings --maxfail=1 2>&1 | tee results/tests_output.txt
# Parse tests_output for summary
python - <<'PY'
from pathlib import Path
s=Path('results/tests_output.txt').read_text()
# Extract passed/failed counts
import re
m = re.search(r"(\d+) passed", s)
passed = int(m.group(1)) if m else 0
m2 = re.search(r"(\d+) failed", s)
failed = int(m2.group(1)) if m2 else 0
report = {'tests_run': passed+failed, 'tests_passed': passed, 'tests_failed': failed}
import json
Path('results/results_post.json').write_text(json.dumps(report, indent=2))
print('Wrote results/results_post.json')
PY
