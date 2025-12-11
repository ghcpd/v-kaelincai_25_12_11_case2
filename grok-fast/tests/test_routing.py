import pytest
from pathlib import Path

from src.graph import Graph
from src.routing import bellman_ford_shortest_path

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "data" / "test_data.json"


@pytest.fixture
def graph():
    return Graph.from_json_file(str(FIXTURE_PATH))


def test_bellman_ford_finds_optimal_path_with_negative_edge(graph):
    """Bellman-Ford should find the optimal path despite negative edge."""
    path, cost = bellman_ford_shortest_path(graph, "A", "B")
    assert path == ["A", "C", "D", "F", "B"]
    assert cost == pytest.approx(1.0)


def test_bellman_ford_no_path(graph):
    """Test no path scenario."""
    with pytest.raises(ValueError, match="No path"):
        bellman_ford_shortest_path(graph, "B", "A")  # Assuming no reverse


def test_bellman_ford_negative_cycle():
    """Test negative cycle detection."""
    g = Graph()
    g.add_edge("A", "B", 1)
    g.add_edge("B", "A", -2)  # Cycle
    with pytest.raises(ValueError, match="negative cycle"):
        bellman_ford_shortest_path(g, "A", "B")