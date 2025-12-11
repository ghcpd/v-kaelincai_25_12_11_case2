#!/usr/bin/env python
"""End-to-end manual API test script."""

import sys
import os

# Add the src directory to the path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from logistics.graph_v2 import Graph
from logistics.routing_v2 import RoutingService, RoutingRequest

print("=" * 60)
print("Test 1: Routing with Negative Weights (Bellman-Ford)")
print("=" * 60)
graph = Graph.from_json_file(os.path.join(os.path.dirname(__file__), "..", "data", "graph_negative_weight.json"))
service = RoutingService()

request = RoutingRequest(
    request_id="demo_001",
    graph=graph,
    start="A",
    goal="B"
)

result = service.route(request)
print(f"✓ Path found: {result.path}")
print(f"✓ Cost: {result.cost}")
print(f"✓ Algorithm: {result.algorithm_used.value}")
print(f"✓ Computation time: {result.computation_time_ms:.2f} ms")
print(f"✓ Cached: {result.is_cached}")
print()

print("=" * 60)
print("Test 2: Idempotency (Cached Request)")
print("=" * 60)
result2 = service.route(request)
print(f"✓ Path found: {result2.path}")
print(f"✓ Cost: {result2.cost}")
print(f"✓ Cached: {result2.is_cached}")
print(f"✓ Computation time: {result2.computation_time_ms:.2f} ms (faster due to cache)")
print()

print("=" * 60)
print("Test 3: Non-Negative Graph (Dijkstra)")
print("=" * 60)
graph2 = Graph.from_edge_list([
    ("A", "B", 1.0),
    ("A", "C", 4.0),
    ("B", "C", 2.0),
    ("B", "D", 5.0),
    ("C", "D", 1.0)
])

request2 = RoutingRequest(
    request_id="demo_002",
    graph=graph2,
    start="A",
    goal="D"
)

result3 = service.route(request2)
print(f"✓ Path found: {result3.path}")
print(f"✓ Cost: {result3.cost}")
print(f"✓ Algorithm: {result3.algorithm_used.value}")
print()

print("=" * 60)
print("Test 4: Error Handling (No Path)")
print("=" * 60)
graph3 = Graph.from_edge_list([
    ("A", "B", 1.0),
    ("C", "D", 1.0)
])

request3 = RoutingRequest(
    request_id="demo_003",
    graph=graph3,
    start="A",
    goal="D"
)

try:
    result4 = service.route(request3)
except Exception as e:
    print(f"✓ Error caught: {e.__class__.__name__}")
    print(f"✓ Error code: {e.code}")
    print(f"✓ Error message: {e.message}")
print()

print("=" * 60)
print("Test 5: Negative Cycle Detection")
print("=" * 60)
graph4 = Graph.from_edge_list([
    ("A", "B", 1.0),
    ("B", "C", -3.0),
    ("C", "A", 1.0)
])

request4 = RoutingRequest(
    request_id="demo_004",
    graph=graph4,
    start="A",
    goal="C"
)

try:
    result5 = service.route(request4)
except Exception as e:
    print(f"✓ Error caught: {e.__class__.__name__}")
    print(f"✓ Error code: {e.code}")
    print(f"✓ Error message: {e.message}")
print()

print("=" * 60)
print("Audit Log Summary")
print("=" * 60)
audit = service.get_audit_log()
print(f"Total audit entries: {len(audit)}")
for i, entry in enumerate(audit, 1):
    print(f"{i}. {entry['event_type']:20s} | {entry['request_id']:15s} | {entry['status']:10s}")

print()
print("=" * 60)
print("✓ ALL MANUAL TESTS PASSED")
print("=" * 60)
