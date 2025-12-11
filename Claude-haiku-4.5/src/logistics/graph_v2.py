"""
v2 Graph module with comprehensive validation.
Extends legacy graph.py with validation layer, metadata, and cycle detection.
"""

from __future__ import annotations

from typing import Dict, Iterable, Tuple, List, Optional, Set
from dataclasses import dataclass
from enum import Enum
import json


class GraphValidationError(Exception):
    """Raised when graph fails validation checks."""
    pass


class GraphClassification(Enum):
    """Classification of graph properties for algorithm selection."""
    HAS_NEGATIVE_WEIGHTS = "has_negative_weights"
    HAS_CYCLE = "has_cycle"
    SAFE_FOR_DIJKSTRA = "safe_for_dijkstra"


@dataclass
class GraphMetadata:
    """Metadata about a graph for caching and algorithm selection."""
    has_negative_weights: bool
    has_cycle: bool
    node_count: int
    edge_count: int
    
    @property
    def safe_for_dijkstra(self) -> bool:
        return not self.has_negative_weights


class Graph:
    """Directed weighted graph with validation and metadata."""

    def __init__(self) -> None:
        self._adj: Dict[str, Dict[str, float]] = {}
        self._metadata: Optional[GraphMetadata] = None

    def add_edge(self, source: str, target: str, weight: float) -> None:
        """Add edge, validating weight."""
        if not isinstance(weight, (int, float)):
            raise GraphValidationError(f"Weight must be numeric, got {type(weight)}")
        if not self._is_finite(weight):
            raise GraphValidationError(f"Weight must be finite, got {weight}")
        if not isinstance(source, str) or not source:
            raise GraphValidationError("Source node must be non-empty string")
        if not isinstance(target, str) or not target:
            raise GraphValidationError("Target node must be non-empty string")
        
        if source not in self._adj:
            self._adj[source] = {}
        self._adj[source][target] = float(weight)
        if target not in self._adj:
            self._adj[target] = {}
        self._metadata = None  # Invalidate cache

    def neighbors(self, node: str) -> Dict[str, float]:
        return self._adj.get(node, {})

    def nodes(self) -> Iterable[str]:
        return self._adj.keys()

    def validate(self) -> None:
        """
        Comprehensive validation:
        - All nodes referenced exist.
        - No isolated nodes (optional enforcement).
        - All weights finite.
        """
        for node in self._adj:
            if not isinstance(node, str) or not node:
                raise GraphValidationError(f"Invalid node: {node}")
            for neighbor, weight in self._adj[node].items():
                if neighbor not in self._adj:
                    raise GraphValidationError(
                        f"Edge ({node} → {neighbor}) references undefined node: {neighbor}"
                    )
                if not self._is_finite(weight):
                    raise GraphValidationError(
                        f"Edge ({node} → {neighbor}) has invalid weight: {weight}"
                    )

    def get_metadata(self) -> GraphMetadata:
        """
        Lazy-load and cache graph metadata (cycle detection, negative weights, etc.).
        """
        if self._metadata is None:
            has_neg = self._has_negative_weights()
            has_cyc = self._has_cycle_dfs()
            self._metadata = GraphMetadata(
                has_negative_weights=has_neg,
                has_cycle=has_cyc,
                node_count=len(list(self.nodes())),
                edge_count=sum(len(neighbors) for neighbors in self._adj.values()),
            )
        return self._metadata

    def _has_negative_weights(self) -> bool:
        """Check if any edge has negative weight."""
        for node in self._adj:
            for _, weight in self._adj[node].items():
                if weight < 0:
                    return True
        return False

    def _has_cycle_dfs(self) -> bool:
        """Detect cycle using DFS (simple approach)."""
        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def has_cycle_dfs_helper(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for neighbor in self._adj.get(node, {}):
                if neighbor not in visited:
                    if has_cycle_dfs_helper(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node)
            return False

        for node in self._adj:
            if node not in visited:
                if has_cycle_dfs_helper(node):
                    return True
        return False

    @staticmethod
    def _is_finite(val: float) -> bool:
        """Check if float is finite (not inf or nan)."""
        return not (val != val or val == float('inf') or val == float('-inf'))

    @staticmethod
    def from_edge_list(edges: Iterable[Tuple[str, str, float]]) -> "Graph":
        g = Graph()
        for src, dst, w in edges:
            g.add_edge(src, dst, w)
        return g

    @classmethod
    def from_json_file(cls, path: str) -> "Graph":
        """Load graph from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        edges: List[Tuple[str, str, float]] = [
            (e["source"], e["target"], float(e["weight"])) for e in data["edges"]
        ]
        graph = cls.from_edge_list(edges)
        graph.validate()
        return graph

    def to_dict(self) -> Dict:
        """Serialize to dict for JSON."""
        edges = []
        for src in self._adj:
            for dst, weight in self._adj[src].items():
                edges.append({"source": src, "target": dst, "weight": weight})
        return {"edges": edges}

    def to_json_str(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
