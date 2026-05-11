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
    
    # 40 mins = 3000m target
    result = generator.generate_loop(1, 27, {"walkability": 1.0})
    
    assert result is not None
    assert len(result.outbound_path) > 0
    assert len(result.return_path) > 0
    assert result.total_distance > 0
