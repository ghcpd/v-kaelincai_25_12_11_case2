from __future__ import annotations

from typing import Dict, List, Tuple, Optional
import math

from .graph import Graph


def bellman_ford_shortest_path(graph: Graph, start: str, goal: str) -> Tuple[List[str], float]:
    """
    Compute shortest path from start to goal using Bellman-Ford algorithm.
    Supports negative weights, detects negative cycles.
    """
    nodes = list(graph.nodes())
    if start not in nodes or goal not in nodes:
        raise ValueError(f"Start or goal node not in graph")

    # Initialize distances
    dist: Dict[str, float] = {node: math.inf for node in nodes}
    dist[start] = 0.0
    prev: Dict[str, Optional[str]] = {node: None for node in nodes}

    edges = graph.edges()

    # Relax edges |V|-1 times
    for _ in range(len(nodes) - 1):
        for u, v, w in edges:
            if dist[u] != math.inf and dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
                prev[v] = u

    # Check for negative cycles
    for u, v, w in edges:
        if dist[u] != math.inf and dist[u] + w < dist[v]:
            raise ValueError("Graph contains a negative cycle")

    if dist[goal] == math.inf:
        raise ValueError(f"No path found from {start} to {goal}")

    return _reconstruct_path(prev, goal), dist[goal]


def _reconstruct_path(prev: Dict[str, Optional[str]], goal: str) -> List[str]:
    path: List[str] = []
    node = goal
    while node is not None:
        path.append(node)
        node = prev.get(node)
    return list(reversed(path))