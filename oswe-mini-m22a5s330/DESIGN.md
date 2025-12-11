# Design & Analysis: Greenfield Appointment Service Replacement

1. Clarifications & Missing Data

- Missing operational telemetry: production logs, p50/p95 latencies, error rates.
- Missing traffic patterns: QPS, peak concurrency, typical payload sizes.
- Missing DB schema snapshots and retention policies.
- Authentication/authorization requirements for external APIs and user identities.
- Disaster recovery and RPO/RTO targets.

Collection checklist (minimum):
- Code: full repository and build artifacts.
- Logs: request traces, error stacks, structured logs with request ids.
- Traffic: historical API traces, 7-day sample with peaks.
- DB snapshots: schema + representative data dumps.
- Monitoring: dashboards (errors, latencies, retries, queue depth).
- Infra: deployment manifests, circuit-breaker configs, retry policies.

Assumptions made for this design:
- System must support 100s RPS with p95 latency < 200ms for simple ops.
- Appointment state transitions are driven by events (request, confirm, finalize).
- External calendar provider(s) are eventually consistent and can fail or be slow.


2. Background Reconstruction (from provided legacy assets)

From the small legacy code (routing/graph tests):
- Business context: core system performs deterministic computations on graphs; key reliability requirement is correctness (optimal path) and correctness under special inputs.
- Core flows: input validation -> algorithm selection -> compute result -> return/raise error on invalid inputs.
- Boundaries: model inputs (graph JSON), compute engine (routing algorithms), test harness.

Uncertainties:
- The original system's external dependencies (DB, caches, scheduler) are not present.
- No API surface for scheduling/appointment semantics—mapping is an abstraction to demonstrate patterns (idempotency, retries, sagas).


3. Current-State Scan & Root-Cause Analysis

Category | Symptom | Likely Root Cause | Evidence / Needed Evidence
---|---|---|---
Functionality | Incorrect path on negative edges | Dijkstra used on graphs with negative weights; early finalize bug | Code comments & tests show failure; KNOWN_ISSUE.md
Reliability | Silent propagation of incorrect results | No input validation; no defensive checks | Tests expect rejection for negative weights; implementation allows it
Performance | Not applicable at given scale | Simplistic algorithm; no profiling data | Need perf traces and traffic
Security | No auth/validation in sample | Small repo lacks auth layers | Clarify with stakeholders
Maintainability | Single-file algorithm with commented bugs | Lacks modularity and test coverage for edge cases | Tests exist but limited
Cost | N/A | N/A | Need infra cost data

High-priority issue: Running Dijkstra on negative-weight graphs.
- Hypothesis: Code lacks negative-edge check and marks nodes visited prematurely; result is suboptimal.
- Validation: Test demonstrates wrong path. Fix paths: add preflight check rejecting negative weights or replace with Bellman-Ford; alternatively fix visited logic.


4. New System Design (Greenfield Replacement)

Target state goals:
- Clear capability boundaries: API layer, Scheduler service (stateful), Adapter for external calendar providers, Audit & Reconciliation service, and Observability.
- Resiliency: idempotency keys for create/update, retry with exponential backoff for external calls, circuit-breaker per provider, timeouts, and compensating actions using Saga/outbox.
- Consistency: eventual consistency using a transactional outbox and reconcilers to ensure no missed state transitions.

Service decomposition:
- service/appointments API (HTTP+gRPC boundary)
- service/scheduler: state machine and durable queue (e.g., PostgreSQL or DynamoDB + stream)
- service/adapters/calendar: provider adapter with circuit breaker and rate limiting
- service/audit: reconciliation and reporting
- shared/lib: idempotency, outbox, metrics, structured logging

Unified state machine (appointments):
- states: created -> requested -> confirmed -> finalized | cancelled | failed
- transitions guarded by idempotency and versioning (optimistic concurrency)

Idempotency & Retry strategy:
- Every client-supplied create/update carries an idempotency key; server stores results for TTL (24h by default).
- External provider calls wrapped with retry + exponential backoff (e.g., 100ms * 2^n up to cap).
- Circuit breaker per provider (open after N failures in rolling window) and health check to re-close.

Compensation (Saga/outbox):
- Use a transactional outbox: write state change + outgoing message in same DB txn; background dispatcher reads outbox and performs side effects.
- If provider confirms then subsequent compensation is no-op; if provider fails after a few retries, post 'compensate' event to cancel or reschedule.

Architecture diagram (ASCII):

Client -> API Gateway -> App Service -> Scheduler DB (state + outbox)
                                          |-> Outbox Dispatcher -> Calendar Adapter -> Provider
                                          |-> Reconciler -> Audit DB

Key interfaces / Schemas (example):
- CreateAppointmentRequest
  - idempotency_key: str (<=36), required
  - user_id: str, required
  - start_ts: ISO8601 datetime, required
  - duration_minutes: int, 1..1440
  - metadata: object (opaque)

- Appointment record (DB):
  - appointment_id: UUID
  - user_id, start_ts, duration, state: enum
  - version: int (for optimistic concurrency)
  - created_at, updated_at

Validation constraints:
- start_ts must be in future (or within configurable window)
- duration 1..1440
- metadata size limit 2KB

Migration & Parallel Run
- Shadow traffic: route a % of read/write to new service in dual-write mode. Use write-discovery with idempotency keys to avoid double side effects.
- Backfill: export legacy data to new schema, run reconciliation to upsert states.
- Cutover: once reconciliation gap is under threshold, promote new service and route 100% traffic.
- Rollback: stop writes on new service, replay any pending outbox items in legacy-compatible format.


5. Testing & Acceptance (Dynamically Generated)

Top crash points converted into tests (at least 5):

Test 1: Healthy path
- Preconditions: calendar provider healthy mock
- Steps: create appointment -> expect confirmed
- Outcome: appointment in 'confirmed' state; outbox empty; metric success rate 100%
- Observability: logs contain request_id, attempt=1, provider_latency < 200ms

Test 2: Idempotency
- Preconditions: same idempotency_key sent twice
- Steps: call create twice quickly
- Outcome: second call returns same appointment_id and does not create duplicate; provider called once
- Observability: logs show idempotency_key lookup hit and returned cached result

Test 3: Retry & Backoff
- Preconditions: provider fails 2 times then succeeds
- Steps: create appointment
- Outcome: provider called 3 times; appointment confirmed; metrics show retries=2; backoff intervals respected
- Observability: timing assertions on retry backoffs

Test 4: Timeout + Circuit Breaker
- Preconditions: provider times out repeatedly
- Steps: create appointment until circuit opens
- Outcome: appointment marked 'failed' after max retries; circuit breaker enters open state; subsequent calls short-circuit
- Observability: metric circuit_state=open; logs show short-circuit errors

Test 5: Compensation / Saga
- Preconditions: provider acknowledges but later webhook indicates slot conflict
- Steps: create appointment; later provider sends conflict webhook
- Outcome: scheduler triggers compensation (cancel/notify user); audit entry created; reconciliation fixes inconsistent state
- Observability: outbox contains compensate event; audit record shows before/after snapshot

Acceptance criteria (sample):
- Given a create request, When provider responds OK, Then appointment moves to 'confirmed' within 2s (p95 <2s), success_rate >= 99.5%
- Given transient provider failures, When retries are enabled, Then final success rate >= 99% with <=4 retries


6. Structured Logging & Observability

Logging schema (JSON):
{
  "ts": "ISO8601",
  "request_id": "uuid",
  "service": "appointments",
  "level": "INFO/ERROR/DEBUG",
  "event": "create_request|provider_call|compensation",
  "appointment_id": "uuid (masked partial)",
  "user_id": "masked",
  "idempotency_key": "<redacted last 8 chars>",
  "duration_ms": 123,
  "retry_attempt": 2,
  "error": "optional stack"
}

Sensitive fields (user email, phone) are redacted in logs; idempotency_key is partially masked.

7. One-click test fixture

- run_tests.sh: runs pytest, then collects metrics (success rates, retries, idempotency asserts) into results/ directory.
- outputs include pass/fail, aggregated metrics JSON, and a compare report (baseline vs current).


Deliverables (files created in this repo):
- src/: AppointmentService prototype + adapters + idempotency/outbox
- mocks/: calendar mock supporting immediate/delayed/failing behaviors
- data/: test_data.json with ≥5 canonical cases
- tests/: integration tests described above
- logs/: sample logs
- results/: results_post.json + aggregated_metrics.json
- requirements.txt, setup.sh, run_tests.sh
- compare_report.md: rollout guidance

