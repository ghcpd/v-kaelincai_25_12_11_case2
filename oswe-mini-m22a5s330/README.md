# Appointment Service (Greenfield Replacement)

This repository contains a small greenfield prototype for a resilient appointment scheduling service, designed as a replacement for a legacy system. It includes design notes, tests, and a one-click test harness.

See DESIGN.md for architecture, migration plan, and test cases.

Quickstart:

- Create a virtualenv and install deps: pip install -r requirements.txt
- Run tests: ./run_tests.sh

Project quick commands (Windows PowerShell):

1) Run tests: $env:PYTHONPATH = "$env:PYTHONPATH;$(Resolve-Path -Relative src);$(Get-Location)"; python -m pytest -q oswe-mini-m22a5s330/tests
2) Aggregate results: python oswe-mini-m22a5s330/scripts/aggregate_results.py
3) Compute metrics: python oswe-mini-m22a5s330/scripts/compute_metrics.py


Project layout
- src/: runtime implementation (AppointmentService)
- mocks/: calendar API mock with configurable behavior
- data/: test data
- tests/: integration test suites (idempotency, retries, timeout, sagas, reconciliation)
- logs/: example logs
- results/: test outputs and metrics
- run_tests.sh: run pytest and collect artifacts
- setup.sh: environment setup helper
- DESIGN.md: analysis and architecture deliverable
- compare_report.md: rollout guidance & metrics
