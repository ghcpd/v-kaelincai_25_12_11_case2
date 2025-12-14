# Compare Report (Pre vs Post)

This greenfield replacement is designed to mitigate issues observed in the legacy `dijkstra`-based routing sample by:
- Adding idempotency to avoid duplicate appointments
- Implementing outbox pattern to decouple DB write from external side-effects
- Providing retry/backoff with configurable parameters
- Exposing endpoints for replay and monitoring

Metrics to collect:
- SLO: 99% of create requests either succeed or have outbox enqueued within 500ms
- Error rate: Target <1% of requests returning 5xx; transient errors cause outbox retry
- Latency: p50/p95 of create calls under moderate load

Rollout guidance:
- Start in shadow mode (dual-write) using a feature flag; validate consistency via reconciliation.
- Monitor outbox queue size and replay success rate; set an alert threshold for outbox growth.
- Use schema validation and a small compatibility layer to transform legacy API payloads to new model.

