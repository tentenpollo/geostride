"""
Routing Service

Implements Dijkstra and A* pathfinding with custom vibe-weighted costs.
"""
import heapq
import math
from collections.abc import Callable
from dataclasses import dataclass

import networkx as nx

from geostride.core.logging import get_logger
from geostride.services.cost_functions import CostFunctionEngine
from geostride.services.vibe_engine import VibeEngine, VibeProfile

logger = get_logger(__name__)


@dataclass
class RoutingResult:
    """Result of a routing operation."""
    path_nodes: list[int]
    path_coords: list[tuple[float, float]]  # (lat, lon) tuples
    total_distance: float  # meters
    total_time: float  # seconds
    vibe_profile: VibeProfile
    nodes_explored: int
    algorithm: str


class RoutingService:
    """
    Handles pathfinding with vibe-weighted costs.
    
    Implements both Dijkstra and A* algorithms with custom weight functions
    derived from the Generative Cost Function.
    """
    
    def __init__(
        self,
        graph: nx.MultiDiGraph,
        cost_engine: CostFunctionEngine,
        vibe_engine: VibeEngine
    ):
        self.graph = graph
        self.cost_engine = cost_engine
        self.vibe_engine = vibe_engine
    
    def _heuristic(self, node1: int, node2: int) -> float:
        """
        A* heuristic: Haversine distance between nodes.
        
        Admissible heuristic for geographic routing.
        """
        n1 = self.graph.nodes[node1]
        n2 = self.graph.nodes[node2]
        
        lat1, lon1 = math.radians(n1['y']), math.radians(n1['x'])
        lat2, lon2 = math.radians(n2['y']), math.radians(n2['x'])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return 6371000 * c  # Earth radius in meters
    
    def dijkstra(
        self,
        origin_node: int,
        dest_node: int,
        weight_func: Callable[[int, int, dict], float]
    ) -> RoutingResult:
        """
        Find shortest path using Dijkstra's algorithm.
        
        Args:
            origin_node: Starting node ID
            dest_node: Destination node ID
            weight_func: Function(u, v, data) -> cost
            
        Returns:
            RoutingResult with path and metrics
        """
        # Priority queue: (cost, node, path)
        heap = [(0, origin_node, [origin_node])]
        visited = set()
        nodes_explored = 0
        
        while heap:
            cost, current, path = heapq.heappop(heap)
            
            if current in visited:
                continue
            
            visited.add(current)
            nodes_explored += 1
            
            if current == dest_node:
                return self._build_result(path, nodes_explored, "dijkstra")
            
            # Explore neighbors
            for neighbor in self.graph.neighbors(current):
                if neighbor not in visited:
                    # Get edge data (use first edge for multigraph)
                    edge_data = self.graph[current][neighbor][0]
                    edge_cost = weight_func(current, neighbor, edge_data)
                    new_cost = cost + edge_cost
                    heapq.heappush(heap, (new_cost, neighbor, path + [neighbor]))
        
        # No path found
        raise ValueError(f"No path found between nodes {origin_node} and {dest_node}")
    
    def astar(
        self,
        origin_node: int,
        dest_node: int,
        weight_func: Callable[[int, int, dict], float]
    ) -> RoutingResult:
        """
        Find shortest path using A* algorithm.
        
        Uses Haversine distance as the heuristic.
        
        Args:
            origin_node: Starting node ID
            dest_node: Destination node ID  
            weight_func: Function(u, v, data) -> cost
            
        Returns:
            RoutingResult with path and metrics
        """
        # Priority queue: (f_score, g_score, node, path)
        # f_score = g_score + heuristic
        h = self._heuristic(origin_node, dest_node)
        heap = [(h, 0, origin_node, [origin_node])]
        
        g_scores = {origin_node: 0}
        visited = set()
        nodes_explored = 0
        
        while heap:
            f_score, g_score, current, path = heapq.heappop(heap)
            
            if current in visited:
                continue
            
            visited.add(current)
            nodes_explored += 1
            
            if current == dest_node:
                return self._build_result(path, nodes_explored, "astar")
            
            for neighbor in self.graph.neighbors(current):
                if neighbor in visited:
                    continue
                
                edge_data = self.graph[current][neighbor][0]
                edge_cost = weight_func(current, neighbor, edge_data)
                tentative_g = g_score + edge_cost
                
                if neighbor not in g_scores or tentative_g < g_scores[neighbor]:
                    g_scores[neighbor] = tentative_g
                    h = self._heuristic(neighbor, dest_node)
                    f = tentative_g + h
                    heapq.heappush(heap, (f, tentative_g, neighbor, path + [neighbor]))
        
        raise ValueError(f"No path found between nodes {origin_node} and {dest_node}")
    
    def _build_result(
        self,
        path_nodes: list[int],
        nodes_explored: int,
        algorithm: str
    ) -> RoutingResult:
        """Build a RoutingResult from a path with full road geometry."""
        # Build coordinate list with full edge geometries
        coords = []
        edge_data_list = []
        total_distance = 0.0
        
        for i in range(len(path_nodes)):
            u = path_nodes[i]
            
            # Add node coordinate
            node_data = self.graph.nodes[u]
            node_coord = (node_data['y'], node_data['x'])  # lat, lon
            
            if i == 0:
                # First node - just add it
                coords.append(node_coord)
            else:
                # Get edge from previous node to this node
                prev = path_nodes[i-1]
                edge_data = self.graph[prev][u][0]
                edge_data_list.append(edge_data)
                total_distance += edge_data.get('length', 0)
                
                # Check if edge has geometry (LineString with intermediate points)
                if 'geometry' in edge_data:
                    # Extract all points from the geometry LineString
                    geom = edge_data['geometry']
                    # shapely LineString coords are (lon, lat), need to convert to (lat, lon)
                    edge_coords = [(lat, lon) for lon, lat in geom.coords]
                    
                    # Add edge coordinates (skip first if it matches last coord to avoid duplicates)
                    if edge_coords:
                        if coords and edge_coords[0] == coords[-1]:
                            coords.extend(edge_coords[1:])
                        else:
                            coords.extend(edge_coords)
                else:
                    # No geometry - just add the node coordinate
                    coords.append(node_coord)
        
        # Estimate time (4.5 km/h = 1.25 m/s)
        total_time = total_distance / 1.25
        
        # Compute vibe profile for the route
        vibe_profile = self.vibe_engine.compute_route_vibe_profile(coords, edge_data_list)
        
        return RoutingResult(
            path_nodes=path_nodes,
            path_coords=coords,
            total_distance=total_distance,
            total_time=total_time,
            vibe_profile=vibe_profile,
            nodes_explored=nodes_explored,
            algorithm=algorithm
        )
    
    def find_shortest_path(
        self,
        origin_node: int,
        dest_node: int
    ) -> RoutingResult | None:
        """
        Find shortest path using Dijkstra with default (length-only) weights.

        Returns None if no path exists between the nodes.
        """
        try:
            weight_func = self.cost_engine.create_weight_function(
                self.graph, {}, 'length'
            )
            return self.dijkstra(origin_node, dest_node, weight_func)
        except ValueError:
            return None

    def find_route(
        self,
        origin_node: int,
        dest_node: int,
        vibe_weights: dict[str, float],
        algorithm: str = "astar"
    ) -> RoutingResult:
        """
        Find optimal route considering vibes.
        
        Args:
            origin_node: Starting node
            dest_node: Ending node
            vibe_weights: User's vibe preferences
            algorithm: "dijkstra" or "astar"
            
        Returns:
            RoutingResult with full path info
        """
        weight_func = self.cost_engine.create_weight_function(
            self.graph,
            vibe_weights,
            base_weight='length'
        )
        
        if algorithm == "dijkstra":
            return self.dijkstra(origin_node, dest_node, weight_func)
        else:
            return self.astar(origin_node, dest_node, weight_func)
    
    def find_route_avoiding_edges(
        self,
        origin_node: int,
        dest_node: int,
        vibe_weights: dict[str, float],
        avoided_edges: set[tuple[int, int]],
        algorithm: str = "astar"
    ) -> RoutingResult:
        """
        Find route while avoiding specific edges.
        
        Used for loop generation to ensure disjoint return path.
        
        Args:
            origin_node: Starting node
            dest_node: Ending node
            vibe_weights: User's vibe preferences
            avoided_edges: Set of (u, v) tuples to avoid
            algorithm: Routing algorithm
            
        Returns:
            RoutingResult
        """
        base_weight_func = self.cost_engine.create_weight_function(
            self.graph,
            vibe_weights,
            base_weight='length'
        )
        
        def penalized_weight_func(u: int, v: int, data: dict) -> float:
            base_cost = base_weight_func(u, v, data)
            
            # Heavily penalize avoided edges (but don't completely block)
            if (u, v) in avoided_edges or (v, u) in avoided_edges:
                return base_cost * 100  # 100x penalty
            
            return base_cost
        
        if algorithm == "dijkstra":
            return self.dijkstra(origin_node, dest_node, penalized_weight_func)
        else:
            return self.astar(origin_node, dest_node, penalized_weight_func)
