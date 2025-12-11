"""
v2 Routing module with unified state machine, idempotency, and resilience.
Provides Dijkstra (non-negative) and Bellman-Ford (negative support) algorithms.
"""

from __future__ import annotations

from typing import Dict, List, Tuple, Optional, NamedTuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import heapq
import time
from datetime import datetime
from abc import ABC, abstractmethod
import hashlib
import json

from .graph_v2 import Graph, GraphValidationError, GraphMetadata


class RequestStatus(Enum):
    """Request lifecycle states."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class AlgorithmType(Enum):
    """Available algorithms."""
    DIJKSTRA = "dijkstra"
    BELLMAN_FORD = "bellman_ford"


class RoutingError(Exception):
    """Base class for routing errors."""
    pass


class ValidationError(RoutingError):
    """Raised on input validation failure."""
    def __init__(self, code: str, message: str, field_errors: Optional[Dict[str, List[str]]] = None):
        self.code = code
        self.message = message
        self.field_errors = field_errors or {}
        super().__init__(message)


class AlgorithmError(RoutingError):
    """Raised when algorithm fails (no path, negative cycle, etc.)."""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class TimeoutError(RoutingError):
    """Raised when computation exceeds timeout."""
    def __init__(self, timeout_ms: int):
        self.timeout_ms = timeout_ms
        super().__init__(f"Computation exceeded {timeout_ms} ms")


class CircuitBreakerOpen(RoutingError):
    """Raised when circuit breaker is open."""
    def __init__(self):
        super().__init__("Circuit breaker is open; service temporarily unavailable")


class AlgorithmChoice(NamedTuple):
    """Algorithm selection with reasoning."""
    algorithm: AlgorithmType
    is_safe: bool
    reason: str


@dataclass
class RoutingRequest:
    """Immutable routing request."""
    request_id: str
    graph: Graph
    start: str
    goal: str
    timeout_ms: int = 5000
    enable_idempotency: bool = True


@dataclass
class RoutingResult:
    """Result of a routing computation."""
    request_id: str
    path: List[str]
    cost: float
    algorithm_used: AlgorithmType
    graph_has_negative_weights: bool
    computation_time_ms: float
    is_cached: bool = False
    timestamp_utc: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dict."""
        d = asdict(self)
        d["algorithm_used"] = self.algorithm_used.value
        d["status"] = "success"
        return d


@dataclass
class AuditLogEntry:
    """Entry in audit log."""
    timestamp: str
    request_id: str
    event_type: str  # ROUTE_REQUESTED, ROUTE_COMPLETED, CACHE_HIT, ERROR, TIMEOUT
    graph_size_nodes: int
    graph_size_edges: int
    start_node: str
    goal_node: str
    algorithm_selected: Optional[str]
    path_cost: Optional[float]
    computation_time_ms: Optional[float]
    status: str  # SUCCESS, CACHED, FAILED, TIMEOUT
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)


class IdempotencyCache:
    """Simple in-memory idempotency cache with TTL."""

    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[RoutingResult, float]] = {}

    def get(self, key: str) -> Optional[RoutingResult]:
        """Retrieve cached result if not expired."""
        if key not in self._cache:
            return None
        result, timestamp = self._cache[key]
        if time.time() - timestamp > self.ttl_seconds:
            del self._cache[key]
            return None
        return result

    def set(self, key: str, result: RoutingResult) -> None:
        """Cache result."""
        self._cache[key] = (result, time.time())

    def invalidate(self, key: str) -> None:
        """Remove cached entry."""
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all entries."""
        self._cache.clear()


class CircuitBreaker:
    """Simple circuit breaker for fault isolation."""

    def __init__(self, failure_threshold: int = 5, timeout_duration_s: int = 30):
        self.failure_threshold = failure_threshold
        self.timeout_duration_s = timeout_duration_s
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "closed"  # closed, open, half_open

    def record_success(self) -> None:
        """Record successful call; reset counter."""
        self.failure_count = 0
        self.state = "closed"

    def record_failure(self) -> None:
        """Record failure; check if should open."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"

    def is_open(self) -> bool:
        """Check if circuit is open, accounting for timeout."""
        if self.state == "open":
            if self.last_failure_time and time.time() - self.last_failure_time > self.timeout_duration_s:
                self.state = "half_open"
                return False
            return True
        return False

    def call(self, fn, *args, **kwargs):
        """Execute function if circuit allows; track result."""
        if self.is_open():
            raise CircuitBreakerOpen()
        try:
            result = fn(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise


def select_algorithm(metadata: GraphMetadata) -> AlgorithmChoice:
    """
    Select appropriate algorithm based on graph properties.
    
    Returns: AlgorithmChoice with algorithm, safety flag, and reasoning.
    """
    if metadata.has_cycle and metadata.has_negative_weights:
        raise AlgorithmError(
            "NEGATIVE_CYCLE",
            "Graph contains both negative weights and cycles; shortest path undefined"
        )
    
    if metadata.has_negative_weights:
        return AlgorithmChoice(
            algorithm=AlgorithmType.BELLMAN_FORD,
            is_safe=True,
            reason="Graph contains negative weights; Bellman-Ford required for correctness."
        )
    
    return AlgorithmChoice(
        algorithm=AlgorithmType.DIJKSTRA,
        is_safe=True,
        reason="All weights non-negative; Dijkstra provides optimal O((V+E) log V) solution."
    )


def dijkstra_shortest_path(graph: Graph, start: str, goal: str, timeout_ms: int = 5000) -> Tuple[List[str], float]:
    """
    Dijkstra's algorithm (non-negative weights only).
    
    Raises:
        ValidationError: if graph has negative weights.
        AlgorithmError: if no path exists.
        TimeoutError: if computation exceeds timeout_ms.
    """
    metadata = graph.get_metadata()
    if metadata.has_negative_weights:
        raise AlgorithmError(
            "NEGATIVE_WEIGHT",
            "Graph contains negative edge weight; Dijkstra is unsafe"
        )
    
    start_time = time.time()

    dist: Dict[str, float] = {start: 0.0}
    prev: Dict[str, Optional[str]] = {start: None}
    heap: List[Tuple[float, str]] = [(0.0, start)]
    visited = set()

    while heap:
        if (time.time() - start_time) > timeout_ms / 1000.0:
            raise TimeoutError(timeout_ms)

        cost, node = heapq.heappop(heap)

        if node == goal:
            return _reconstruct_path(prev, goal), cost

        if cost > dist.get(node, float("inf")):
            continue

        if node in visited:
            continue
        visited.add(node)

        for neighbor, weight in graph.neighbors(node).items():
            if neighbor in visited:
                continue
            new_cost = cost + weight
            if new_cost < dist.get(neighbor, float("inf")):
                dist[neighbor] = new_cost
                prev[neighbor] = node
                heapq.heappush(heap, (new_cost, neighbor))

    raise AlgorithmError("NO_PATH", f"No path found from {start} to {goal}")


def bellman_ford_shortest_path(
    graph: Graph, start: str, goal: str, timeout_ms: int = 5000
) -> Tuple[List[str], float]:
    """
    Bellman-Ford algorithm (supports negative weights, detects negative cycles).
    
    Time complexity: O(V * E)
    
    Raises:
        ValidationError: if start/goal not in graph.
        AlgorithmError: if negative cycle detected or no path exists.
        TimeoutError: if computation exceeds timeout_ms.
    """
    start_time = time.time()
    
    nodes = list(graph.nodes())
    if start not in nodes or goal not in nodes:
        raise AlgorithmError(
            "INVALID_NODE",
            f"Start or goal node not in graph"
        )

    # Initialize distances
    dist: Dict[str, float] = {n: float("inf") for n in nodes}
    prev: Dict[str, Optional[str]] = {n: None for n in nodes}
    dist[start] = 0.0

    # Relax edges |V|-1 times
    for i in range(len(nodes) - 1):
        if (time.time() - start_time) > timeout_ms / 1000.0:
            raise TimeoutError(timeout_ms)

        updated = False
        for u in nodes:
            for v, w in graph.neighbors(u).items():
                if dist[u] + w < dist[v]:
                    dist[v] = dist[u] + w
                    prev[v] = u
                    updated = True
        if not updated:
            break

    # Check for negative cycle
    for u in nodes:
        for v, w in graph.neighbors(u).items():
            if dist[u] + w < dist[v]:
                raise AlgorithmError(
                    "NEGATIVE_CYCLE",
                    "Graph contains a negative-weight cycle; shortest path undefined"
                )

    if dist.get(goal, float("inf")) == float("inf"):
        raise AlgorithmError("NO_PATH", f"No path found from {start} to {goal}")

    return _reconstruct_path(prev, goal), dist[goal]


def _reconstruct_path(prev: Dict[str, Optional[str]], goal: str) -> List[str]:
    """Reconstruct path from predecessor map."""
    path: List[str] = []
    node = goal
    while node is not None:
        path.append(node)
        node = prev.get(node)
    return list(reversed(path))


class RoutingService:
    """
    Unified routing service with state machine, idempotency, and resilience patterns.
    """

    def __init__(
        self,
        cache_ttl_seconds: int = 300,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout_s: int = 30,
    ):
        self.cache = IdempotencyCache(cache_ttl_seconds)
        self.circuit_breaker = CircuitBreaker(circuit_breaker_threshold, circuit_breaker_timeout_s)
        self.audit_log: List[AuditLogEntry] = []

    def route(self, request: RoutingRequest) -> RoutingResult:
        """
        Execute routing request with full state machine, validation, and resilience.
        
        Returns: RoutingResult on success.
        Raises: ValidationError, AlgorithmError, TimeoutError, CircuitBreakerOpen.
        """
        # Step 1: Validate input
        self._validate_request(request)

        # Step 2: Check idempotency cache
        idempotency_key = self._compute_idempotency_key(request)
        if request.enable_idempotency:
            cached = self.cache.get(idempotency_key)
            if cached:
                cached.is_cached = True
                self._log_audit("ROUTE_CACHED", request, cached)
                return cached

        # Step 3: Check circuit breaker
        if self.circuit_breaker.is_open():
            raise CircuitBreakerOpen()

        # Step 4: Graph validation and metadata
        try:
            request.graph.validate()
            metadata = request.graph.get_metadata()
        except Exception as e:
            raise ValidationError("INVALID_GRAPH", str(e))

        # Step 5: Algorithm selection
        try:
            choice = select_algorithm(metadata)
        except AlgorithmError as e:
            self._log_audit_error("ALGORITHM_ERROR", request, e.code, e.message)
            raise

        # Step 6: Run solver with timeout enforcement
        start_time = time.time()
        try:
            if choice.algorithm == AlgorithmType.DIJKSTRA:
                path, cost = dijkstra_shortest_path(request.graph, request.start, request.goal, request.timeout_ms)
            else:
                path, cost = bellman_ford_shortest_path(request.graph, request.start, request.goal, request.timeout_ms)

            computation_time_ms = (time.time() - start_time) * 1000

            # Step 7: Build result and cache
            result = RoutingResult(
                request_id=request.request_id,
                path=path,
                cost=cost,
                algorithm_used=choice.algorithm,
                graph_has_negative_weights=metadata.has_negative_weights,
                computation_time_ms=computation_time_ms,
                is_cached=False,
            )

            if request.enable_idempotency:
                self.cache.set(idempotency_key, result)

            # Step 8: Record success
            self.circuit_breaker.record_success()
            self._log_audit("ROUTE_COMPLETED", request, result)
            return result

        except TimeoutError as e:
            self.circuit_breaker.record_failure()
            self._log_audit_error("TIMEOUT", request, "TIMEOUT_EXCEEDED", e.message)
            raise

        except AlgorithmError as e:
            self._log_audit_error("ALGORITHM_ERROR", request, e.code, e.message)
            raise

        except Exception as e:
            self.circuit_breaker.record_failure()
            self._log_audit_error("INTERNAL_ERROR", request, "INTERNAL_ERROR", str(e))
            raise

    def _validate_request(self, request: RoutingRequest) -> None:
        """Validate request fields."""
        field_errors: Dict[str, List[str]] = {}

        if not request.request_id or len(request.request_id) > 128:
            field_errors.setdefault("request_id", []).append(
                "Must be non-empty string of length ≤ 128"
            )

        if not isinstance(request.start, str) or not request.start:
            field_errors.setdefault("start", []).append("Must be non-empty string")

        if not isinstance(request.goal, str) or not request.goal:
            field_errors.setdefault("goal", []).append("Must be non-empty string")

        if not (100 <= request.timeout_ms <= 60000):
            field_errors.setdefault("timeout_ms", []).append(
                "Must be between 100 and 60000"
            )

        if field_errors:
            raise ValidationError("INVALID_INPUT", "Request validation failed", field_errors)

    def _compute_idempotency_key(self, request: RoutingRequest) -> str:
        """Compute idempotency key from request and graph."""
        graph_json = request.graph.to_json_str()
        key_str = f"{request.request_id}:{request.start}:{request.goal}:{graph_json}"
        return hashlib.sha256(key_str.encode()).hexdigest()

    def _log_audit(self, event_type: str, request: RoutingRequest, result: Optional[RoutingResult] = None) -> None:
        """Log audit entry."""
        metadata = request.graph.get_metadata()
        entry = AuditLogEntry(
            timestamp=datetime.utcnow().isoformat() + "Z",
            request_id=request.request_id,
            event_type=event_type,
            graph_size_nodes=metadata.node_count,
            graph_size_edges=metadata.edge_count,
            start_node=request.start,
            goal_node=request.goal,
            algorithm_selected=result.algorithm_used.value if result else None,
            path_cost=result.cost if result else None,
            computation_time_ms=result.computation_time_ms if result else None,
            status="SUCCESS" if event_type == "ROUTE_COMPLETED" else "CACHED" if event_type == "ROUTE_CACHED" else "UNKNOWN",
        )
        self.audit_log.append(entry)

    def _log_audit_error(self, event_type: str, request: RoutingRequest, error_code: str, error_message: str) -> None:
        """Log error audit entry."""
        metadata = request.graph.get_metadata()
        entry = AuditLogEntry(
            timestamp=datetime.utcnow().isoformat() + "Z",
            request_id=request.request_id,
            event_type=event_type,
            graph_size_nodes=metadata.node_count,
            graph_size_edges=metadata.edge_count,
            start_node=request.start,
            goal_node=request.goal,
            algorithm_selected=None,
            path_cost=None,
            computation_time_ms=None,
            status="FAILED" if event_type != "TIMEOUT" else "TIMEOUT",
            error_code=error_code,
            error_message=error_message,
        )
        self.audit_log.append(entry)

    def get_audit_log(self) -> List[Dict]:
        """Return audit log as list of dicts."""
        return [entry.to_dict() for entry in self.audit_log]
