Executive Summary

- Legacy issue: Algorithmic correctness bug (Dijkstra on negative weights) demonstrates missing input validation and inadequate testing for edge cases.
- Greenfield replacement: Appointment Service prototype illustrating defensive design: idempotency, retry/backoff, circuit-breaker, transactional outbox + simple reconciliation.
- Key improvements: explicit input validation, structured logging with request_id, idempotency keys, outbox for reliable side-effects, test-driven integration tests for common crash points.
- Next steps: expand to persistent storage, durable queues, provider adapter with health endpoints, and SCIM-level auth.
