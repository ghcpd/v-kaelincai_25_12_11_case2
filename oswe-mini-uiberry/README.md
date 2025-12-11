OSWE Mini — Greenfield replacement scaffold

Purpose
- Prototype a greenfield replacement for the legacy "issue_project" appointment flow.
- Provide runnable mocks, a small service runtime, integration tests that exercise crash points (idempotency, retries, timeouts, compensation), and one-click test scripts.

Quick start (Windows / POSIX)
1) Create a venv and install dependencies:
   python -m venv .venv
   .venv\Scripts\activate  # PowerShell/CMD (Windows)
   source .venv/bin/activate # POSIX
   pip install -r requirements.txt

2) Run all tests (one-click):
   bash run_all.sh    # POSIX
   # or on Windows PowerShell:
   .\run_tests.sh

What you'll find
- src/: small appointment service client demonstrating idempotency, retries, timeouts, circuit-breaker and compensation.
- mocks/: mock provider API that simulates success, transient failures, delays, and partial failure requiring compensation.
- tests/: pytest-based integration tests (>=5 canonical test cases) that generate results/results_post.json and logs/log_post.txt.
- data/: canonical test cases and expected outputs.
- run_all.sh / run_tests.sh: automation to run the suite and collect artifacts.
- compare_report.md: guidance for rollout and metrics to compare pre/post.

Notes & assumptions
- This is a focused prototype for architecture, testing and migration patterns — not production-grade code.
- Network calls are simulated against an in-process mock HTTP server; replace mocks with real endpoints for integration testing.

Contact
- Role: Senior architecture & delivery engineer (this scaffold is the starting point for migration planning).