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
    ) -> list[tuple[int, float]]:
        """
        Find potential turnaround points at approximately half target distance.

        Returns list of (node_id, actual_distance) tuples sorted by closeness
        to the ideal half-distance.
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
        return candidates[:num_candidates]

    def _score_turnaround_point(
        self,
        origin_node: int,
        turnaround_node: int,
        vibe_weights: dict[str, float],
        half_distance: float,
        actual_dist: float,
    ) -> float:
        """
        Score a turnaround point based on vibe potential and distance accuracy.

        Higher score = better turnaround point.
        """
        node_data = self.graph.nodes[turnaround_node]
        lat, lon = node_data['y'], node_data['x']

        profile = self.vibe_engine.compute_point_vibe_profile(lat, lon)

        # Weight by user preferences
        vibe_score = 0.0
        weights = 0.0

        if vibe_weights.get('greenery', 0) > 0:
            vibe_score += profile.greenery * vibe_weights['greenery']
            weights += vibe_weights['greenery']
        if vibe_weights.get('blue_space', 0) > 0:
            vibe_score += profile.blue_space * vibe_weights['blue_space']
            weights += vibe_weights['blue_space']
        if vibe_weights.get('safety_check', 0) > 0:
            vibe_score += profile.safety * vibe_weights['safety_check']
            weights += vibe_weights['safety_check']

        vibe_score = vibe_score / weights if weights > 0 else profile.overall

        # Distance accuracy: 1.0 = exactly half_distance, 0.0 = at tolerance edge
        distance_error = abs(actual_dist - half_distance)
        distance_accuracy = max(0.0, 1.0 - (distance_error / half_distance))

        # Blend: 60% vibes, 40% distance accuracy
        return 0.6 * vibe_score + 0.4 * distance_accuracy

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

    def _compute_weighted_overall(
        self,
        profile: VibeProfile,
        vibe_weights: dict[str, float]
    ) -> float:
        """Recompute overall as a weighted average based on user preferences."""
        mapping = {
            'greenery': profile.greenery,
            'blue_space': profile.blue_space,
            'introvert_mode': profile.quietness,
            'extrovert_mode': profile.liveliness,
            'safety_check': profile.safety,
            'walkability': profile.walkability,
        }

        weighted_scores = []
        total_weight = 0.0
        for key, score in mapping.items():
            weight = vibe_weights.get(key, 0)
            if weight > 0:
                weighted_scores.append(score * weight)
                total_weight += weight

        if total_weight == 0:
            # No preferences specified — fall back to simple mean
            return sum(mapping.values()) / len(mapping)

        return sum(weighted_scores) / total_weight

    def _assemble_loop_result(
        self,
        origin_node: int,
        turnaround_node: int,
        outbound_result,
        return_result,
        vibe_weights: dict[str, float]
    ) -> LoopResult:
        """Build a LoopResult from outbound and return routing results."""
        # Collect outbound edges for avoidance
        outbound_edges = set()
        for i in range(len(outbound_result.path_nodes) - 1):
            u, v = outbound_result.path_nodes[i], outbound_result.path_nodes[i + 1]
            outbound_edges.add((u, v))
            outbound_edges.add((v, u))  # Both directions

        # Collect return edges for disjoint calculation
        return_edges = set()
        for i in range(len(return_result.path_nodes) - 1):
            u, v = return_result.path_nodes[i], return_result.path_nodes[i + 1]
            return_edges.add((u, v))

        disjoint_pct = self._calculate_disjoint_percentage(outbound_edges, return_edges)

        # Combine paths (remove duplicate turnaround node)
        full_coords = outbound_result.path_coords + return_result.path_coords[1:]

        # Calculate totals
        total_distance = outbound_result.total_distance + return_result.total_distance
        total_time = outbound_result.total_time + return_result.total_time

        # Compute combined vibe profile with real edge data
        edge_data_list = []
        if outbound_result.edge_data_list:
            edge_data_list.extend(outbound_result.edge_data_list)
        if return_result.edge_data_list:
            edge_data_list.extend(return_result.edge_data_list)

        combined_profile = self.vibe_engine.compute_route_vibe_profile(
            full_coords, edge_data_list if edge_data_list else None
        )

        # Weight overall by user preferences
        combined_profile.overall = self._compute_weighted_overall(
            combined_profile, vibe_weights
        )

        total_explored = outbound_result.nodes_explored + return_result.nodes_explored

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

    def generate_loop(
        self,
        origin_node: int,
        duration_minutes: int,
        vibe_weights: dict[str, float]
    ) -> LoopResult:
        """
        Generate a circular walking route.

        Tries up to 3 turnaround candidates. If a loop exceeds
        1.25x the target distance, falls back to progressively softer
        return-path penalties and tries the next candidate.
        Returns the shortest acceptable loop, or the shortest overall
        if none fall within the tolerance.
        """
        target_distance = self._estimate_target_distance(duration_minutes)
        logger.info(f"Generating loop: {duration_minutes}min = ~{target_distance:.0f}m")

        # Find turnaround candidates with their actual distances
        candidates = self._find_turnaround_candidates(
            origin_node, target_distance, vibe_weights
        )

        if not candidates:
            raise ValueError("Could not find suitable turnaround points for loop")

        # Score candidates (vibes + distance accuracy) and sort descending
        half_distance = target_distance / 2
        scored = [
            (
                c[0],
                self._score_turnaround_point(
                    origin_node, c[0], vibe_weights, half_distance, c[1]
                ),
            )
            for c in candidates
        ]
        scored.sort(key=lambda x: x[1], reverse=True)

        best_result: LoopResult | None = None
        max_candidates = min(3, len(scored))

        for attempt in range(max_candidates):
            turnaround_node = scored[attempt][0]
            logger.info(
                f"Attempt {attempt + 1}/{max_candidates}: "
                f"turnaround node {turnaround_node}"
            )

            try:
                # Route outbound
                outbound_result = self.routing.find_route(
                    origin_node, turnaround_node, vibe_weights, algorithm="astar"
                )

                # Collect outbound edges for avoidance
                outbound_edges = set()
                for i in range(len(outbound_result.path_nodes) - 1):
                    u, v = outbound_result.path_nodes[i], outbound_result.path_nodes[i + 1]
                    outbound_edges.add((u, v))
                    outbound_edges.add((v, u))

                # Route return avoiding outbound path (hard penalty)
                return_result = self.routing.find_route_avoiding_edges(
                    turnaround_node, origin_node, vibe_weights,
                    outbound_edges, algorithm="astar", penalty_multiplier=100.0
                )

                # If return leg alone is excessive, try softer penalty
                if return_result.total_distance > target_distance * 0.6:
                    logger.info(
                        f"Return leg {return_result.total_distance:.0f}m exceeds "
                        f"budget {target_distance * 0.6:.0f}m; trying softer penalty"
                    )
                    return_result = self.routing.find_route_avoiding_edges(
                        turnaround_node, origin_node, vibe_weights,
                        outbound_edges, algorithm="astar", penalty_multiplier=10.0
                    )

                loop_result = self._assemble_loop_result(
                    origin_node, turnaround_node,
                    outbound_result, return_result, vibe_weights
                )

                logger.info(
                    f"Loop attempt {attempt + 1}: "
                    f"{loop_result.total_distance:.0f}m, "
                    f"{loop_result.disjoint_percentage:.0%} disjoint"
                )

                # Accept if within 25% overshoot (Option B)
                if loop_result.total_distance <= target_distance * 1.25:
                    logger.info(
                        f"Accepted loop within tolerance: "
                        f"{loop_result.total_distance:.0f}m"
                    )
                    return loop_result

                # Track best fallback (shortest distance)
                if best_result is None or loop_result.total_distance < best_result.total_distance:
                    best_result = loop_result

            except ValueError as e:
                logger.warning(
                    f"Attempt {attempt + 1} failed for node {turnaround_node}: {e}"
                )
                continue

        if best_result is None:
            raise ValueError(
                "Could not generate a valid loop with any turnaround candidate"
            )

        logger.info(
            f"No loop within 25% tolerance; falling back to shortest: "
            f"{best_result.total_distance:.0f}m"
        )
        return best_result
