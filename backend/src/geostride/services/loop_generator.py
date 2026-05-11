"""
Loop Generator Service

Generates circular walking routes with the Return Path Constraint:
The return path must be as disjoint as possible from the outbound path.

Implements bi-directional A* with edge exclusion for the advanced algorithm.
"""
import heapq
from dataclasses import dataclass

import networkx as nx

from geostride.core.logging import get_logger
from geostride.services.cost_functions import CostFunctionEngine
from geostride.services.routing import RoutingService
from geostride.services.vibe_engine import VibeEngine, VibeProfile

logger = get_logger(__name__)


@dataclass
class LoopResult:
    """Result of loop generation."""
    outbound_path: list[int]
    return_path: list[int]
    full_path_coords: list[tuple[float, float]]
    total_distance: float
    total_time: float
    vibe_profile: VibeProfile
    nodes_explored: int
    disjoint_percentage: float  # How much of return path is unique


class LoopGenerator:
    """
    Generates circular walking routes.
    
    Algorithm (Advanced Bi-directional A* with penalized revisit):
    1. Estimate target distance from duration
    2. Find a "turnaround point" at roughly half the target distance
    3. Route outbound using A* with vibes
    4. Route return using A* with heavy penalties on outbound edges
    5. The penalty encourages exploration of alternative paths
    """
    
    # Walking speed: 4.5 km/h = 75 m/min
    WALKING_SPEED_M_PER_MIN = 75
    
    def __init__(
        self,
        graph: nx.MultiDiGraph,
        routing_service: RoutingService,
        cost_engine: CostFunctionEngine,
        vibe_engine: VibeEngine
    ):
        self.graph = graph
        self.routing = routing_service
        self.cost_engine = cost_engine
        self.vibe_engine = vibe_engine
    
    def _estimate_target_distance(self, duration_minutes: int) -> float:
        """Convert duration to target distance in meters."""
        return duration_minutes * self.WALKING_SPEED_M_PER_MIN
    
    def _find_turnaround_candidates(
        self,
        origin_node: int,
        target_distance: float,
        vibe_weights: dict[str, float],
        num_candidates: int = 5
    ) -> list[int]:
        """
        Find potential turnaround points at approximately half target distance.
        
        Uses a modified BFS/Dijkstra to find nodes at target distance.
        """
        half_distance = target_distance / 2
        tolerance = half_distance * 0.2  # 20% tolerance
        
        weight_func = self.cost_engine.create_weight_function(
            self.graph, vibe_weights, 'length'
        )
        
        # Dijkstra-like exploration to find nodes at target distance
        heap = [(0, origin_node)]
        distances = {origin_node: 0}
        candidates = []
        
        while heap and len(candidates) < num_candidates * 3:
            dist, node = heapq.heappop(heap)
            
            # Check if this node is at approximately the right distance
            if half_distance - tolerance <= dist <= half_distance + tolerance:
                candidates.append((node, dist))
            
            # Don't explore beyond 1.5x target
            if dist > half_distance * 1.5:
                continue
            
            for neighbor in self.graph.neighbors(node):
                edge_data = self.graph[node][neighbor][0]
                edge_cost = weight_func(node, neighbor, edge_data)
                new_dist = dist + edge_cost
                
                if neighbor not in distances or new_dist < distances[neighbor]:
                    distances[neighbor] = new_dist
                    heapq.heappush(heap, (new_dist, neighbor))
        
        # Sort by how close they are to ideal distance and return top candidates
        candidates.sort(key=lambda x: abs(x[1] - half_distance))
        return [c[0] for c in candidates[:num_candidates]]
    
    def _score_turnaround_point(
        self,
        origin_node: int,
        turnaround_node: int,
        vibe_weights: dict[str, float]
    ) -> float:
        """
        Score a turnaround point based on vibe potential.
        
        Higher score = better turnaround point.
        """
        node_data = self.graph.nodes[turnaround_node]
        lat, lon = node_data['y'], node_data['x']
        
        profile = self.vibe_engine.compute_point_vibe_profile(lat, lon)
        
        # Weight by user preferences
        score = 0.0
        weights = 0.0
        
        if vibe_weights.get('greenery', 0) > 0:
            score += profile.greenery * vibe_weights['greenery']
            weights += vibe_weights['greenery']
        if vibe_weights.get('blue_space', 0) > 0:
            score += profile.blue_space * vibe_weights['blue_space']
            weights += vibe_weights['blue_space']
        if vibe_weights.get('safety_check', 0) > 0:
            score += profile.safety * vibe_weights['safety_check']
            weights += vibe_weights['safety_check']
        
        return score / weights if weights > 0 else profile.overall
    
    def _calculate_disjoint_percentage(
        self,
        outbound_edges: set[tuple[int, int]],
        return_edges: set[tuple[int, int]]
    ) -> float:
        """Calculate what percentage of return path is unique."""
        if not return_edges:
            return 0.0
        
        # Count edges in return that aren't in outbound
        unique_return = 0
        for edge in return_edges:
            reverse = (edge[1], edge[0])
            if edge not in outbound_edges and reverse not in outbound_edges:
                unique_return += 1
        
        return unique_return / len(return_edges)
    
    def generate_loop(
        self,
        origin_node: int,
        duration_minutes: int,
        vibe_weights: dict[str, float]
    ) -> LoopResult:
        """
        Generate a circular walking route.
        
        Args:
            origin_node: Starting/ending node
            duration_minutes: Target walk duration
            vibe_weights: User's vibe preferences
            
        Returns:
            LoopResult with full loop path
        """
        target_distance = self._estimate_target_distance(duration_minutes)
        logger.info(f"Generating loop: {duration_minutes}min = ~{target_distance:.0f}m")
        
        # Find turnaround candidates
        candidates = self._find_turnaround_candidates(
            origin_node, target_distance, vibe_weights
        )
        
        if not candidates:
            raise ValueError("Could not find suitable turnaround points for loop")
        
        # Score and select best turnaround point
        scored = [
            (c, self._score_turnaround_point(origin_node, c, vibe_weights))
            for c in candidates
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        turnaround_node = scored[0][0]
        
        logger.info(f"Selected turnaround node: {turnaround_node}")
        
        # Route outbound
        outbound_result = self.routing.find_route(
            origin_node, turnaround_node, vibe_weights, algorithm="astar"
        )
        
        # Collect outbound edges for avoidance
        outbound_edges = set()
        for i in range(len(outbound_result.path_nodes) - 1):
            u, v = outbound_result.path_nodes[i], outbound_result.path_nodes[i+1]
            outbound_edges.add((u, v))
            outbound_edges.add((v, u))  # Both directions
        
        # Route return avoiding outbound path
        return_result = self.routing.find_route_avoiding_edges(
            turnaround_node, origin_node, vibe_weights,
            outbound_edges, algorithm="astar"
        )
        
        # Collect return edges for disjoint calculation
        return_edges = set()
        for i in range(len(return_result.path_nodes) - 1):
            u, v = return_result.path_nodes[i], return_result.path_nodes[i+1]
            return_edges.add((u, v))
        
        disjoint_pct = self._calculate_disjoint_percentage(outbound_edges, return_edges)
        
        # Combine paths (remove duplicate turnaround node)
        _full_path_nodes = outbound_result.path_nodes + return_result.path_nodes[1:]
        full_coords = outbound_result.path_coords + return_result.path_coords[1:]
        
        # Calculate totals
        total_distance = outbound_result.total_distance + return_result.total_distance
        total_time = outbound_result.total_time + return_result.total_time
        
        # Compute combined vibe profile
        combined_profile = self.vibe_engine.compute_route_vibe_profile(full_coords)
        
        total_explored = outbound_result.nodes_explored + return_result.nodes_explored
        
        logger.info(
            f"Loop generated: {total_distance:.0f}m, "
            f"{disjoint_pct:.0%} disjoint return path"
        )
        
        return LoopResult(
            outbound_path=outbound_result.path_nodes,
            return_path=return_result.path_nodes,
            full_path_coords=full_coords,
            total_distance=total_distance,
            total_time=total_time,
            vibe_profile=combined_profile,
            nodes_explored=total_explored,
            disjoint_percentage=disjoint_pct
        )
    

