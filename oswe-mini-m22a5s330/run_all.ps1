# Run all tests and aggregate results (PowerShell)
$env:PYTHONPATH = "$env:PYTHONPATH;$(Resolve-Path -Relative src);$(Get-Location)"
python -m pytest -q oswe-mini-m22a5s330/tests
python .\oswe-mini-m22a5s330\scripts\aggregate_results.py
Write-Host "Artifacts written to oswe-mini-m22a5s330\results\aggregated_metrics.json"