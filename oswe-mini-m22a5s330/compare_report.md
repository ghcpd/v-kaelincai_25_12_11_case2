# Compare Report (Prototype)

This report compares pre-change baseline (legacy) and the greenfield prototype. For this exercise the legacy system is minimal, so focus is on migration strategy and test results.

Metrics to collect:
- pass/fail per test
- retry counts
- idempotency assertions
- p50/p95 latencies for provider calls

Rollout guidance:
- Start with shadow mode: duplicate requests to the new service but do not surface to users.
- Run reconciliation for 24h and ensure mismatch < 0.1%.
- Gradually ramp traffic (5% -> 25% -> 50% -> 100%) while monitoring retries, errors, and latencies.

Rollback guidance:
- Pause new-service writes, let outbox drain, and then revert routing.
