# Run all projects and collect artifacts
# Assume issue_project and grok-fast are siblings

# Run legacy
cd ..\issue_project
python -m venv .venv; .\.venv\Scripts\activate; pip install -r requirements.txt; pytest --json-report --json-report-file=results_pre.json

# Run new
cd ..\grok-fast
python -m venv .venv; .\.venv\Scripts\activate; pip install -r requirements.txt; pytest --json-report --json-report-file=results\results_post.json

# Collect to Shared
cp ..\issue_project\results_pre.json Shared\results\
cp results\results_post.json Shared\results\