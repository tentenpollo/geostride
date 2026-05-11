"""
Execution Service - Routing Pipeline

Orchestrates the full route generation pipeline:
1. Loads the OSM graph for the target area
2. Applies vibe-weighted cost functions to the graph
3. Generates a circular walking route via the loop generator
4. Returns the route as GeoJSON with metadata and execution details
"""
import time
import networkx as nx
from typing import Optional
from geostride.core.logging import get_logger

from geostride.models import (
    ExecuteRequest,
    ExecuteResponse,
    GeoJSONFeatureCollection,
    GeoJSONFeature,
    GeoJSONGeometry,
    RouteMetadata,
    VibeBreakdown,
    ExecutionDetails
)
from geostride.services.graph_loader import GraphLoader
from geostride.services.cost_functions import CostFunctionEngine
from geostride.services.vibe_engine import VibeEngine
from geostride.services.routing import RoutingService
from geostride.services.loop_generator import LoopGenerator
from geostride.utils.geo import haversine_distance

logger = get_logger(__name__)


class ExecutionService:
    """Orchestrates the route generation pipeline from graph loading to GeoJSON output."""
    
    def __init__(
        self,
        graph_loader: GraphLoader,
        graph: nx.MultiDiGraph,
        cost_engine: CostFunctionEngine,
        vibe_engine: VibeEngine,
        routing_service: RoutingService,
        loop_generator: LoopGenerator
    ):
        self.graph_loader = graph_loader
        self.graph = graph
        self.cost_engine = cost_engine
        self.vibe_engine = vibe_engine
        self.routing_service = routing_service
        self.loop_generator = loop_generator
    
    def execute(self, request: ExecuteRequest) -> ExecuteResponse:
        """Load the graph, apply vibe-weighted costs, generate a circular route, and return GeoJSON."""
        start_time = time.time()
        
        try:
            # Get nearest node to origin
            logger.info(f"Finding nearest node to origin: lat={request.origin.lat}, lon={request.origin.lon}")
            
            # Debug: Check graph bounds
            import networkx as nx
            nodes = list(self.graph.nodes(data=True))
            lats = [data['y'] for _, data in nodes]
            lons = [data['x'] for _, data in nodes]
            logger.info(f"Graph bounds: lat [{min(lats):.6f}, {max(lats):.6f}], lon [{min(lons):.6f}, {max(lons):.6f}]")
            logger.info(f"Total nodes in graph: {len(nodes)}")
            
            # Find all nodes within 500m of origin
            nearby_nodes = []
            for node_id, node_data in nodes:
                node_lat, node_lon = node_data['y'], node_data['x']
                dist = haversine_distance(request.origin.lat, request.origin.lon, node_lat, node_lon)
                if dist < 500:
                    nearby_nodes.append((node_id, dist))
            nearby_nodes.sort(key=lambda x: x[1])
            logger.info(f"Nodes within 500m of origin: {len(nearby_nodes)}")
            if nearby_nodes:
                logger.info(f"Closest 5 nodes: {nearby_nodes[:5]}")
            
            origin_node = self.graph_loader.get_nearest_node(
                request.origin.lat,
                request.origin.lon
            )
            # Verify the node coordinates
            node_lat, node_lon = self.graph_loader.get_node_coords(origin_node)
            logger.info(f"OSMnx nearest node {origin_node} is at lat={node_lat}, lon={node_lon}")
            
            # Check distance from requested origin
            dist = haversine_distance(request.origin.lat, request.origin.lon, node_lat, node_lon)
            logger.info(f"Distance from requested origin to nearest node: {dist:.1f} meters")
            
            # If nearest node is too far (>200m), check if we need to reload graph
            if dist > 200:
                logger.warning(f"Nearest node is {dist:.1f}m away - walking network may be sparse at this location")
                if not nearby_nodes:
                    logger.error(f"No walking network nodes within 500m of origin! This area may not have mapped footpaths.")
                    # Try to find closest node regardless of distance
                    closest_node = None
                    closest_dist = float('inf')
                    for node_id, node_data in nodes:
                        node_lat, node_lon = node_data['y'], node_data['x']
                        d = haversine_distance(request.origin.lat, request.origin.lon, node_lat, node_lon)
                        if d < closest_dist:
                            closest_dist = d
                            closest_node = node_id
                    if closest_node and closest_dist < dist:
                        logger.info(f"Using manually found closest node {closest_node} at {closest_dist:.1f}m")
                        origin_node = closest_node
                        node_lat, node_lon = self.graph_loader.get_node_coords(origin_node)
            
            # Add no-go zones if provided
            for zone in request.no_go_zones:
                center_lat = sum(v.lat for v in zone.vertices) / len(zone.vertices)
                center_lon = sum(v.lon for v in zone.vertices) / len(zone.vertices)
                self.vibe_engine.add_no_go_zone(center_lat, center_lon, radius_meters=150)
            
            # Execute loop generation (always circular as per requirements)
            loop_result = self.loop_generator.generate_loop(
                origin_node,
                request.duration_minutes,
                request.vibes.model_dump()
            )
            
            # Calculate execution time
            execution_time_ms = (time.time() - start_time) * 1000
            
            # Build GeoJSON
            coords = [[lon, lat] for lat, lon in loop_result.full_path_coords]
            
            # Verify route starts at expected location
            if loop_result.full_path_coords:
                first_lat, first_lon = loop_result.full_path_coords[0]
                logger.info(f"Route first coordinate: lat={first_lat}, lon={first_lon}")
                logger.info(f"Requested origin: lat={request.origin.lat}, lon={request.origin.lon}")
                dist_from_origin = haversine_distance(
                    request.origin.lat, request.origin.lon, first_lat, first_lon
                )
                logger.info(f"Route start is {dist_from_origin:.1f} meters from requested origin")
            
            geojson = GeoJSONFeatureCollection(
                features=[
                    GeoJSONFeature(
                        geometry=GeoJSONGeometry(coordinates=coords),
                        properties={
                            "stroke": "#22c55e",
                            "stroke-width": 4,
                            "stroke-opacity": 0.8,
                            "route_type": "circular_loop",
                            "disjoint_percentage": loop_result.disjoint_percentage
                        }
                    )
                ]
            )
            
            # Build vibe breakdown
            vibe_breakdown = VibeBreakdown(
                greenery=loop_result.vibe_profile.greenery,
                blue_space=loop_result.vibe_profile.blue_space,
                quietness=loop_result.vibe_profile.quietness,
                liveliness=loop_result.vibe_profile.liveliness,
                safety=loop_result.vibe_profile.safety,
                walkability=loop_result.vibe_profile.walkability,
                overall=loop_result.vibe_profile.overall
            )
            
            # Build metadata
            metadata = RouteMetadata(
                distance_meters=loop_result.total_distance,
                estimated_duration_minutes=loop_result.total_time / 60,
                vibe_score=loop_result.vibe_profile.overall,
                vibe_breakdown=vibe_breakdown
            )
            
            # Build execution details (for demystification)
            execution_details = ExecutionDetails(
                algorithm="dijkstra",
                nodes_explored=loop_result.nodes_explored,
                graph_size=f"{self.graph.number_of_nodes():,} nodes, {self.graph.number_of_edges():,} edges",
                disjoint_percentage=loop_result.disjoint_percentage,
                execution_time_ms=execution_time_ms
            )
            
            logger.info(
                f"Route executed: {loop_result.total_distance:.0f}m, "
                f"{loop_result.nodes_explored} nodes explored, "
                f"{execution_time_ms:.0f}ms"
            )
            
            return ExecuteResponse(
                success=True,
                geojson=geojson,
                metadata=metadata,
                execution_details=execution_details
            )
            
        except Exception as e:
            logger.error(f"Route execution failed: {e}")
            raise ValueError(f"Route generation failed: {str(e)}")
    
    def get_graph_info(self) -> dict:
        """Get information about the loaded graph."""
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "region": self.graph_loader._current_region or "unknown"
        }
