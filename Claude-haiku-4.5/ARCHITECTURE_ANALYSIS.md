# Greenfield Logistics Routing System – Architecture & Delivery Plan

**Baseline Legacy System:** `issue_project/`
**Target Replacement:** `Claude-haiku-4.5/` (v2)
**Prepared:** December 2025

---

## Executive Summary

The legacy **Dijkstra-based routing system** exhibits a critical **algorithmic failure**: it:
- **Lacks input validation** for negative edge weights (precondition for Dijkstra).
- **Prematurely finalizes nodes**, preventing cost relaxation necessary for correctness.
- **Silently returns suboptimal paths** without error, creating production risk.

**Greenfield Replacement Strategy:**
1. Implement a **unified state machine** for routing requests (Pending → In-Progress → Completed/Failed).
2. **Validate all inputs** before algorithm invocation; reject invalid graphs or route to appropriate solver.
3. Use **Bellman-Ford algorithm** (supports negative weights) as the default, with Dijkstra as an optimized fallback for non-negative-weight graphs.
4. Apply **idempotency, retry/backoff, timeout propagation, and circuit-breaker patterns** for production resilience.
5. Provide a **transactional outbox pattern** for audit logging and compensation.
6. **Mirror the legacy interface** for zero-change cutover, with optional v2 enhancements.

---

## 1. Current-State Analysis

### 1.1 Visible Assets & Known Issue

| Artifact | Summary |
|----------|---------|
| **KNOWN_ISSUE.md** | Dijkstra fails on negative-weight edges; nodes marked visited too early. |
| **routing.py** | Naive Dijkstra with early visit marking and *no negative-edge check*. |
| **graph.py** | Adjacency-dict structure; JSON loader; no validation layer. |
| **test data** | `graph_negative_weight.json` with edge D→F = -3. |
| **tests** | Two tests: (a) expect ValueError on negative weights, (b) expect Bellman-Ford to find optimal path (cost=1). |

### 1.2 Root-Cause Chain

| Layer | Issue | Evidence | Impact |
|-------|-------|----------|--------|
| **Algorithm** | Dijkstra designed for non-negative weights. | Classic algorithm theory. | Wrong results on negative edges. |
| **Implementation** | Early visit marking (line: `visited.add(neighbor)` on discovery). | `routing.py:42` marks visited before finalization. | Prevents relaxation; locks in suboptimal costs. |
| **Input Validation** | No check for precondition (weight ≥ 0). | Lines 18–20 loop but don't validate sign. | Silent failure; no error signal. |
| **Error Handling** | No exception raised on invalid input. | dijkstra_shortest_path() assumes valid graph. | User unaware of graph unsuitability. |

### 1.3 Functional Gaps

| Category | Gap | Severity |
|----------|-----|----------|
| **Correctness** | Suboptimal paths on graphs with any negative edge. | **CRITICAL** – production routing errors. |
| **Observability** | No request ID, audit trail, or call context. | **HIGH** – hard to debug customer issues. |
| **Resilience** | No retry, idempotency, timeout, or circuit-breaker. | **HIGH** – transient failures cause 5xx errors. |
| **Scalability** | No async support, no batch processing, no caching. | **MEDIUM** – fine for light loads but limits growth. |
| **Testing** | Only two unit tests; no integration/stress/chaos tests. | **MEDIUM** – hidden edge cases. |

---

## 2. Greenfield Target Design

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Client (Legacy or v2)                │
└──────────┬────────────────────────────────────────────────┘
           │
           ↓ POST /routing/v1 or /routing/v2
┌─────────────────────────────────────────────────────────┐
│     Unified Routing Service (Request Handler)            │
│  • Request ID generation & context injection             │
│  • Input validation & rate limiting                      │
└──────────┬────────────────────────────────────────────────┘
           │
           ↓
┌─────────────────────────────────────────────────────────┐
│        Routing State Machine (Pending → Running → OK/Err) │
│  • Idempotency key lookup (request_id, graph_id)        │
│  • Timeout & circuit-breaker enforcement                │
│  • Audit/event emission                                 │
└──────────┬────────────────────────────────────────────────┘
           │
           ↓
┌─────────────────────────────────────────────────────────┐
│       Graph Input Validator & Preprocessor               │
│  • Check: all weights defined, no invalid node refs      │
│  • Classify: has_negative_weight, has_cycle             │
│  • Transform: normalize, cache metadata                  │
└──────────┬────────────────────────────────────────────────┘
           │
           ├─ Negative edges? ────→ Route to Bellman-Ford
           ├─ Non-negative? ──────→ Route to Dijkstra (faster)
           └─ Cycle detected? ────→ Reject or use appropriate solver
           │
           ↓
┌─────────────────────────────────────────────────────────┐
│     Algorithm Dispatch & Execution (Timeout-aware)       │
│  • Dijkstra (non-negative, faster)                      │
│  • Bellman-Ford (negative weights, slower)              │
│  • Error: negative cycle, no path, timeout              │
└──────────┬────────────────────────────────────────────────┘
           │
           ↓
┌─────────────────────────────────────────────────────────┐
│        Transactional Outbox & Audit Log                  │
│  • Append: request, graph state, algorithm choice,      │
│    path result, cost, duration, errors                  │
│  • Idempotency check: if (request_id, graph_id) exists, │
│    return cached result without re-running              │
└──────────┬────────────────────────────────────────────────┘
           │
           ↓
┌─────────────────────────────────────────────────────────┐
│     Response & Structured Logging                        │
│  • 200 OK: {request_id, path, cost, duration_ms, ...}   │
│  • 400 Bad Request: {code, message, field_errors}       │
│  • 408 Timeout / 503 Circuit-Breaker                    │
│  • Log: level=INFO, fields=(request_id, path, algorithm,│
│         cost, latency, idempotent_cache_hit)            │
└──────────┬────────────────────────────────────────────────┘
           │
           ↓ (200, 4xx, 5xx with detailed errors & observability)
           Client
```

### 2.2 State Machine

```
┌──────────┐
│ Pending  │  request_id generated, request queued
└─────┬────┘
      │ begin_processing()
      ↓
┌──────────────────┐
│  In_Progress     │  graph validated, algorithm selected, solving
└─────┬────────────┘
      │
      ├─ resolve(path, cost) ──→ ┌──────────────┐
      │                          │  Completed   │
      │                          └──────────────┘
      │
      ├─ reject(error) ──────────→ ┌──────────────┐
      │                           │  Failed      │
      │                           └──────────────┘
      │
      └─ timeout_elapsed() ───────→ ┌──────────────┐
                                   │  Timed_Out   │
                                   └──────────────┘
```

**State Transitions:**
- **Pending** → **In_Progress**: On request acceptance (idempotency check passed).
- **In_Progress** → **Completed**: On algorithm success.
- **In_Progress** → **Failed**: On validation/algorithm error.
- **In_Progress** → **Timed_Out**: On timeout threshold exceeded.
- **Completed/Failed/Timed_Out** → **Pending** (cache hit): Direct return on idempotent retry.

### 2.3 API & Data Contracts

#### Request (v2, backward-compatible with v1)

```json
{
  "request_id": "req_1702300800_abcd1234",
  "graph": {
    "edges": [
      {"source": "A", "target": "B", "weight": 5.0},
      {"source": "A", "target": "C", "weight": 2.0},
      {"source": "C", "target": "D", "weight": 1.0},
      {"source": "D", "target": "F", "weight": -3.0},
      {"source": "F", "target": "B", "weight": 1.0}
    ]
  },
  "start": "A",
  "goal": "B",
  "timeout_ms": 5000,
  "enable_idempotency": true
}
```

**Field Constraints:**
- `request_id` (string): Unique, alphanumeric + underscore, ≤128 chars. **Required** (auto-generated if omitted).
- `graph.edges` (array): ≤10,000 edges per request.
- `edges[].weight` (float): Valid finite number; ±infinity rejected.
- `start`, `goal` (string): Non-empty, ≤128 chars; must exist in graph.
- `timeout_ms` (integer, optional): Default 5000, range [100, 60000].
- `enable_idempotency` (boolean, optional): Default true.

#### Response (Success)

```json
{
  "request_id": "req_1702300800_abcd1234",
  "status": "success",
  "path": ["A", "C", "D", "F", "B"],
  "cost": 1.0,
  "algorithm_used": "bellman_ford",
  "graph_has_negative_weights": true,
  "computation_time_ms": 2.3,
  "is_cached": false,
  "timestamp_utc": "2025-12-11T14:00:00.000Z"
}
```

#### Response (Error – Validation)

```json
{
  "request_id": "req_1702300800_abcd1234",
  "status": "error",
  "code": "INVALID_INPUT",
  "message": "Start node 'X' not found in graph",
  "field_errors": {
    "start": ["Must exist in graph.edges as source or target"]
  },
  "timestamp_utc": "2025-12-11T14:00:00.000Z"
}
```

#### Response (Error – Timeout / Circuit-Breaker)

```json
{
  "request_id": "req_1702300800_abcd1234",
  "status": "error",
  "code": "TIMEOUT_EXCEEDED",
  "message": "Routing computation exceeded 5000 ms",
  "timestamp_utc": "2025-12-11T14:00:00.000Z"
}
```

### 2.4 Algorithm Selection Logic

```python
def select_algorithm(graph: Graph) -> AlgorithmChoice:
    """
    Classify graph and recommend algorithm.
    
    Returns: AlgorithmChoice(algorithm, is_safe, reason)
    """
    has_neg_weight = any(
        weight < 0 
        for node in graph.nodes() 
        for _, weight in graph.neighbors(node).items()
    )
    has_cycle = detect_cycle(graph)  # DFS-based
    
    if has_cycle and has_neg_weight:
        raise ValueError("Graph has negative cycle; shortest path undefined")
    
    if has_neg_weight:
        return AlgorithmChoice(
            algorithm="bellman_ford",
            is_safe=True,
            reason="Graph contains negative weights; Dijkstra unsafe. Bellman-Ford guarantees optimality."
        )
    else:
        return AlgorithmChoice(
            algorithm="dijkstra",
            is_safe=True,
            reason="All weights non-negative; Dijkstra is optimal and faster."
        )
```

### 2.5 Idempotency & Retry Strategy

**Idempotency Key:** `hash(request_id + graph_id + start + goal)`

**Retry Policy:**
- **Max Retries:** 3
- **Backoff:** Exponential (100 ms, 200 ms, 400 ms base; jitter ±25%)
- **Retryable Errors:** Timeout (408), Circuit-Breaker (503), transient network errors.
- **Non-Retryable:** Validation errors (400), algorithm errors (500 if deterministic).

**Cache TTL:** 300 seconds (configurable). Cache key = `idempotency_key`.

### 2.6 Observability & Audit Trail

**Structured Logging Schema:**

```json
{
  "timestamp": "2025-12-11T14:00:00.123Z",
  "level": "INFO",
  "logger_name": "routing_v2",
  "request_id": "req_1702300800_abcd1234",
  "event_type": "routing_completed",
  "context": {
    "graph_id": "graph_neg_weight_001",
    "start_node": "A",
    "goal_node": "B",
    "graph_size_nodes": 6,
    "graph_size_edges": 7,
    "graph_has_negative_weights": true,
    "algorithm_selected": "bellman_ford",
    "path_found": ["A", "C", "D", "F", "B"],
    "path_cost": 1.0,
    "computation_time_ms": 2.3,
    "is_idempotent_cache_hit": false,
    "timeout_ms": 5000,
    "http_status": 200
  },
  "sensitive_fields_masked": false
}
```

**Audit Log (append-only):**

| timestamp | request_id | event_type | graph_id | start | goal | algorithm | path_cost | duration_ms | status |
|-----------|-----------|------------|----------|-------|------|-----------|-----------|------------|--------|
| 2025-12-11T14:00:00 | req_001 | ROUTE_REQUESTED | graph_001 | A | B | bellman_ford | 1.0 | 2.3 | SUCCESS |
| 2025-12-11T14:00:01 | req_001 | ROUTE_CACHED | graph_001 | A | B | (cached) | 1.0 | 0.1 | CACHE_HIT |

---

## 3. Implementation Roadmap

### Phase 1: Core Solver (Week 1)
- ✅ **v2 Graph module** with validation (no changes to structure, add validation layer).
- ✅ **v2 Routing module** with Bellman-Ford + Dijkstra + selection logic.
- ✅ **Unit tests** for both algorithms, edge cases.

### Phase 2: Service Layer (Week 2)
- ✅ **State machine** (Pending → In-Progress → Completed/Failed/Timed_Out).
- ✅ **Idempotency layer** (request_id + graph_id lookup, cache, TTL).
- ✅ **Input validator** (node existence, weight finiteness, bounds).
- ✅ **Structured logging & audit trail**.

### Phase 3: Resilience (Week 3)
- ✅ **Timeout enforcement** (with proper exception bubbling).
- ✅ **Circuit-breaker pattern** (fail-fast after N consecutive timeouts).
- ✅ **Retry + backoff** (exponential, with jitter).

### Phase 4: Integration & Testing (Week 4)
- ✅ **5+ integration tests** (happy path, negative weights, timeout, idempotency, circuit-breaker).
- ✅ **Smoke tests & chaos tests** (random graphs, large graphs, concurrent requests).
- ✅ **Shadow traffic / dual-write** test (legacy + v2 side-by-side).

### Phase 5: Migration & Rollout (Week 5)
- ✅ **Cutover playbook** (read-only mirror → shadow traffic → 5/50/100% traffic shift).
- ✅ **Rollback procedure** (kill switch, feature flags).
- ✅ **Metrics & SLO dashboard** (success rate, latency p50/p95/p99, error rate).

---

## 4. Risk & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|-----------|
| **Bellman-Ford slower on large graphs** | Medium | Performance regression. | Optimize: (a) batch requests, (b) early termination if no updates, (c) Dijkstra fallback for non-negative graphs. |
| **Idempotency cache poisoning** | Low | Stale results returned. | TTL + versioning; invalidate on graph schema change. |
| **Timeout edge case (interruption during solve)** | Medium | Partial results or resource leak. | Graceful cancellation token; resource cleanup in finally block. |
| **Negative cycle not detected** | Low | Infinite loop or slow convergence. | Explicit cycle detection before solving; configurable max iterations. |
| **Concurrent request races** | Medium | Duplicate processing, cache inconsistency. | Atomic idempotency check (DB lock or CAS); request deduplication queue. |

---

## 5. Success Criteria & Acceptance

### Functional
1. ✅ Dijkstra **rejects** graphs with negative weights (or auto-switches algorithm).
2. ✅ Bellman-Ford **finds optimal path** on `graph_negative_weight.json` (cost = 1.0).
3. ✅ No path found → **clear error** (not silent failure).
4. ✅ Negative cycle detection + rejection.

### Non-Functional
1. ✅ **Latency**: p50 ≤ 5 ms, p95 ≤ 50 ms (on graphs ≤1000 edges).
2. ✅ **Availability**: 99.9% (4.3 min/month downtime allowed).
3. ✅ **Correctness**: 100% path optimality on all test cases.
4. ✅ **Idempotency**: Repeated requests with same `request_id` return same result within TTL.

### Testing
1. ✅ ≥95% code coverage (excluding CLI/HTTP bindings).
2. ✅ 5+ integration tests (happy, error, timeout, idempotency, circuit-breaker).
3. ✅ Chaos test: random large graphs, concurrent load, timeout injection.
4. ✅ Regression test: all legacy test cases pass in v2.

---

## 6. Appendices

### A. Data Model & Database Schema (Optional)

If persistence needed (for audit trail):

```sql
CREATE TABLE routing_requests (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  request_id VARCHAR(128) UNIQUE NOT NULL,
  graph_id VARCHAR(128),
  start_node VARCHAR(128) NOT NULL,
  goal_node VARCHAR(128) NOT NULL,
  status ENUM('pending', 'in_progress', 'completed', 'failed', 'timed_out'),
  algorithm_selected VARCHAR(50),
  path JSON,
  cost FLOAT,
  error_code VARCHAR(50),
  error_message TEXT,
  computation_time_ms INT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP NULL,
  UNIQUE INDEX idx_idempotency (request_id, graph_id)
);

CREATE TABLE routing_audit_log (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  request_id VARCHAR(128) NOT NULL,
  event_type VARCHAR(50),
  graph_size_nodes INT,
  graph_size_edges INT,
  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  details JSON,
  FOREIGN KEY (request_id) REFERENCES routing_requests(request_id)
);
```

### B. Configuration Schema

```yaml
routing_service:
  timeouts:
    default_ms: 5000
    min_ms: 100
    max_ms: 60000
  
  idempotency:
    enabled: true
    cache_ttl_seconds: 300
  
  circuit_breaker:
    enabled: true
    failure_threshold: 5  # consecutive failures
    timeout_duration_seconds: 30
    half_open_requests: 3
  
  retry:
    max_retries: 3
    base_delay_ms: 100
    max_delay_ms: 5000
    jitter_percent: 25
  
  logging:
    level: INFO
    format: json
    include_graph_snapshot: false  # privacy
    mask_sensitive_fields: true
```

---

## 7. Glossary

| Term | Definition |
|------|-----------|
| **Idempotency** | Same request (same request_id + graph) always returns same result, regardless of retries. |
| **Bellman-Ford** | Shortest-path algorithm supporting negative weights; O(VE) complexity. |
| **Dijkstra** | Shortest-path algorithm for non-negative weights; O((V+E) log V) with min-heap. |
| **Circuit Breaker** | Fail-fast mechanism that stops calling a service after N consecutive failures. |
| **Outbox Pattern** | Transactional log for audit trail; consumed asynchronously for events. |
| **State Machine** | Finite set of states (Pending, In-Progress, etc.) with defined transitions. |

---

**Next:** Proceed to implementation in `v2/` subdirectory. All code, tests, and scripts provided in subsequent sections.
