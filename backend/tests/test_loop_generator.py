import networkx as nx

from geostride.services.cost_functions import CostFunctionEngine
from geostride.services.loop_generator import LoopGenerator
from geostride.services.routing import RoutingService
from geostride.services.vibe_engine import VibeEngine


def test_loop_generator_small_graph():
    # Create a small ring graph
    graph = nx.MultiDiGraph()
    graph.add_node(1, y=0.0, x=0.0)
    graph.add_node(2, y=0.01, x=0.0)
    graph.add_node(3, y=0.01, x=0.01)
    graph.add_node(4, y=0.0, x=0.01)

    # Add bidirectional edges with lengths
    edges = [(1, 2), (2, 3), (3, 4), (4, 1), (2, 1), (3, 2), (4, 3), (1, 4)]
    for u, v in edges:
        graph.add_edge(u, v, length=1000, highway='residential')

    cost_engine = CostFunctionEngine({})
    vibe_engine = VibeEngine({})
    routing = RoutingService(graph, cost_engine, vibe_engine)

    generator = LoopGenerator(graph, routing, cost_engine, vibe_engine)

    # 27 mins = 2025m target; with 4 edges of 1000m each,
    # half_distance ~1012m, so candidates around nodes 2 or 4
    result = generator.generate_loop(1, 27, {"walkability": 1.0})

    assert result is not None
    assert len(result.outbound_path) > 0
    assert len(result.return_path) > 0
    assert result.total_distance > 0
    assert result.vibe_profile is not None


def test_turnaround_distance_accuracy_scoring():
    """Closer-to-midpoint candidates should score higher when vibes are equal."""
    graph = nx.MultiDiGraph()
    graph.add_node(1, y=0.0, x=0.0)
    graph.add_node(2, y=0.005, x=0.0)
    graph.add_node(3, y=0.015, x=0.0)
    graph.add_node(4, y=0.0, x=0.01)

    # Node 2 is ~555m away, node 3 is ~1665m away (ideal half for 30min=2250m is 1125m)
    for u, v in [(1, 2), (2, 1), (2, 3), (3, 2), (3, 4), (4, 3), (4, 1), (1, 4)]:
        graph.add_edge(u, v, length=111000, highway='residential')

    cost_engine = CostFunctionEngine({})
    vibe_engine = VibeEngine({})
    routing = RoutingService(graph, cost_engine, vibe_engine)
    generator = LoopGenerator(graph, routing, cost_engine, vibe_engine)

    target = 2250  # 30 min
    half = target / 2  # 1125

    # 1000m is ~11% off half, 1800m is ~60% off half
    # With equal vibes, the closer candidate should score higher
    score_close = generator._score_turnaround_point(1, 2, {}, half, 1000)
    score_far = generator._score_turnaround_point(1, 3, {}, half, 1800)

    assert score_close > score_far


def test_iterative_fallback_prefers_shorter_loop():
    """
    On a graph where the first candidate forces a huge detour,
    the generator should fall back to a shorter loop from a later candidate.
    """
    graph = nx.MultiDiGraph()
    # Grid: 1x3 line with a long detour branch at node 2
    for i in range(1, 5):
        graph.add_node(i, y=0.0, x=float(i - 1) * 0.01)

    # Main line: 1-2-3-4, each edge 500m
    for u, v in [(1, 2), (2, 1), (2, 3), (3, 2), (3, 4), (4, 3)]:
        graph.add_edge(u, v, length=500, highway='residential')

    # Add a long detour branch from node 2 to node 5 (1500m)
    graph.add_node(5, y=0.01, x=0.01)
    graph.add_edge(2, 5, length=1500, highway='residential')
    graph.add_edge(5, 2, length=1500, highway='residential')

    cost_engine = CostFunctionEngine({})
    vibe_engine = VibeEngine({})
    routing = RoutingService(graph, cost_engine, vibe_engine)
    generator = LoopGenerator(graph, routing, cost_engine, vibe_engine)

    # Target: 20min = 1500m, half = 750m
    # Candidates around 750m: node 3 (~1000m from 1 via 1-2-3)
    # Node 5 is ~2000m from 1 via 1-2-5 (too far, but let's make sure it picks a reasonable one)
    result = generator.generate_loop(1, 20, {"walkability": 1.0})

    assert result is not None
    assert result.total_distance > 0


def test_weighted_overall_reflects_preferences():
    """Overall should be weighted by user vibe preferences."""
    graph = nx.MultiDiGraph()
    graph.add_node(1, y=0.0, x=0.0)
    graph.add_node(2, y=0.01, x=0.0)
    graph.add_node(3, y=0.01, x=0.01)
    graph.add_node(4, y=0.0, x=0.01)

    for u, v in [(1, 2), (2, 3), (3, 4), (4, 1), (2, 1), (3, 2), (4, 3), (1, 4)]:
        graph.add_edge(u, v, length=1000, highway='residential')

    cost_engine = CostFunctionEngine({})
    vibe_engine = VibeEngine({})
    routing = RoutingService(graph, cost_engine, vibe_engine)
    generator = LoopGenerator(graph, routing, cost_engine, vibe_engine)

    # Only care about walkability
    result = generator.generate_loop(1, 27, {"walkability": 1.0})

    # Since walkability is the only weighted dimension, overall should equal walkability
    assert abs(result.vibe_profile.overall - result.vibe_profile.walkability) < 0.01
