Compare report — Greenfield replacement prototype

Summary
- Prototype demonstrates idempotency, retry-with-backoff, timeout handling, circuit-breaker, and compensation (Saga/outbox-like) patterns.
- Tests exercise five canonical risk cases and emit logs and aggregated results in results/results_post.json.

Key correctness diffs to track during rollout
- Functional correctness: booking reached confirmed state vs. compensated/failed.
- Latency: p50/p95 per flow (not yet measured in prototype — add metrics capture in production).
- Retries and idempotency: duplicate suppression and retry counts.

p50 / p95 guidance (prototype)
- Aim: p50 < 200ms for happy path; p95 < 800ms for provider-dependent flows.
- Circuit-breaker: open after 3 failures within 30s, reset after 60s.

Rollout guidance
1. Shadow traffic: run v2 in shadow mode for 2 weeks; compare booking outcomes and latencies.
2. Dual-write with reconciliation: use transactional outbox in v2; compare provider-side states daily.
3. Read-cutover: Migrate reads to v2 after reconciliation stability (>99.99% match for 48h).
4. Write cutover: Gradual traffic ramp (1%, 5%, 25%, 100%) with automatic rollback if error rate > 0.5% or latency degradation > 2x.

Observability & alerts
- Metrics: success_rate, retry_count, idempotency_hit_rate, mean_latency, p95_latency, circuit_open_count, compensation_count.
- Alerts: success_rate < 99% over 5m, compensation_count spike > 10x baseline, circuit_open_count > 0.

Artifacts
- logs/log_post.txt — structured JSON lines for each request
- results/results_post.json — aggregated outcome summary

Notes
- This is a prototype; productionization requires durable outbox, distributed tracing, RBAC and secrets handling.
