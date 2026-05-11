import networkx as nx

from geostride.services.cost_functions import CostFunctionEngine
from geostride.services.routing import RoutingService
from geostride.services.vibe_engine import VibeEngine


def build_synthetic_grid(nodes_per_side: int = 3) -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    for i in range(nodes_per_side):
        for j in range(nodes_per_side):
            node_id = i * nodes_per_side + j
            graph.add_node(node_id, y=float(i) * 0.01, x=float(j) * 0.01)
    for i in range(nodes_per_side):
        for j in range(nodes_per_side):
            current = i * nodes_per_side + j
            if j + 1 < nodes_per_side:
                right = current + 1
                graph.add_edge(current, right, length=1000, highway="residential")
                graph.add_edge(right, current, length=1000, highway="residential")
            if i + 1 < nodes_per_side:
                down = current + nodes_per_side
                graph.add_edge(current, down, length=1000, highway="residential")
                graph.add_edge(down, current, length=1000, highway="residential")
    return graph


def test_dijkstra_finds_path():
    graph = build_synthetic_grid(3)
    cost_engine = CostFunctionEngine({})
    vibe_engine = VibeEngine({})
    routing = RoutingService(graph, cost_engine, vibe_engine)

    result = routing.find_shortest_path(0, 8)
    assert result is not None
    assert len(result.path_nodes) > 1
    assert result.total_distance > 0


def test_no_path_returns_none():
    graph = nx.MultiDiGraph()
    graph.add_node(0, y=0.0, x=0.0)
    graph.add_node(1, y=0.01, x=0.01)
    cost_engine = CostFunctionEngine({})
    vibe_engine = VibeEngine({})
    routing = RoutingService(graph, cost_engine, vibe_engine)

    result = routing.find_shortest_path(0, 1)
    assert result is None
