"""
Generative Cost Function Engine

Implements the core formula: Cg = C_base * (1 - Quality_Score)

This "demystifies" the routing by showing how vibes translate to edge weights.
"""
import networkx as nx
from typing import Optional
from dataclasses import dataclass
import math

from geostride.utils.geo import haversine_distance


@dataclass
class EdgeVibeScores:
    """Individual vibe scores for an edge."""
    greenery: float = 0.5
    blue_space: float = 0.5
    quietness: float = 0.5
    liveliness: float = 0.5
    lighting: float = 0.5
    walkability: float = 0.5


class CostFunctionEngine:
    """
    Computes generative edge costs based on vibe preferences.
    
    The Generative Cost Function transforms base edge costs (distance/time)
    into "vibe-aware" costs that prefer edges matching user preferences.
    
    Formula: Cg = C_base * (1 - Quality_Score)
    
    Where:
    - C_base is the original edge length or travel time
    - Quality_Score is in [0, 1] based on how well the edge matches vibes
    - Result: High quality edges get lower costs (preferred)
    """
    
    # OSM highway types and their base characteristics
    HIGHWAY_QUIETNESS = {
        "footway": 0.95,
        "pedestrian": 0.90,
        "path": 0.85,
        "living_street": 0.80,
        "residential": 0.70,
        "service": 0.60,
        "unclassified": 0.50,
        "tertiary": 0.40,
        "secondary": 0.25,
        "primary": 0.15,
        "trunk": 0.05,
        "motorway": 0.0,
    }
    
    HIGHWAY_WALKABILITY = {
        "footway": 1.0,
        "pedestrian": 0.95,
        "path": 0.90,
        "living_street": 0.85,
        "residential": 0.75,
        "service": 0.60,
        "unclassified": 0.50,
        "tertiary": 0.40,
        "secondary": 0.20,
        "primary": 0.10,
        "trunk": 0.0,
        "motorway": 0.0,
    }
    
    def __init__(self, amenities: dict):
        """
        Initialize with preloaded amenities.
        
        Args:
            amenities: Dict with keys 'parks', 'water', 'shops', 'food', etc.
        """
        self.amenities = amenities
        self._park_coords = [
            (p['lat'], p['lon']) for p in amenities.get('parks', [])
        ]
        self._water_coords = [
            (w['lat'], w['lon']) for w in amenities.get('water', [])
        ]
        self._shop_coords = [
            (s['lat'], s['lon']) for s in amenities.get('shops', [])
        ]
        self._food_coords = [
            (f['lat'], f['lon']) for f in amenities.get('food', [])
        ]
    

    
    def _count_nearby_pois(
        self,
        lat: float, lon: float,
        poi_list: list[tuple[float, float]],
        radius_meters: float = 100
    ) -> int:
        """Count POIs within radius of a point."""
        count = 0
        for poi_lat, poi_lon in poi_list:
            dist = haversine_distance(lat, lon, poi_lat, poi_lon)
            if dist <= radius_meters:
                count += 1
        return count
    
    def compute_edge_vibe_scores(
        self,
        edge_data: dict,
        u_lat: float, u_lon: float,
        v_lat: float, v_lon: float
    ) -> EdgeVibeScores:
        """
        Compute individual vibe scores for an edge.
        
        Args:
            edge_data: Edge attributes from the graph
            u_lat, u_lon: Start node coordinates
            v_lat, v_lon: End node coordinates
            
        Returns:
            EdgeVibeScores with values in [0, 1]
        """
        # Midpoint for POI proximity checks
        mid_lat = (u_lat + v_lat) / 2
        mid_lon = (u_lon + v_lon) / 2
        
        highway = edge_data.get('highway', 'unclassified')
        if isinstance(highway, list):
            highway = highway[0]
        
        # Greenery score: Based on nearby parks
        parks_nearby = self._count_nearby_pois(mid_lat, mid_lon, self._park_coords, 150)
        greenery = min(1.0, parks_nearby / 2) if parks_nearby > 0 else 0.05  # Low default to penalize non-green areas
        
        # Blue space score: Based on nearby water
        water_nearby = self._count_nearby_pois(mid_lat, mid_lon, self._water_coords, 200)
        blue_space = min(1.0, water_nearby / 1.5) if water_nearby > 0 else 0.2
        
        # Quietness score: Based on highway type
        quietness = self.HIGHWAY_QUIETNESS.get(highway, 0.5)
        
        # Liveliness score: Based on nearby shops/food
        shops_nearby = self._count_nearby_pois(mid_lat, mid_lon, self._shop_coords, 100)
        food_nearby = self._count_nearby_pois(mid_lat, mid_lon, self._food_coords, 100)
        liveliness = min(1.0, (shops_nearby + food_nearby) / 5)
        
        # Lighting score: From OSM 'lit' tag or inferred from highway type
        lit_tag = edge_data.get('lit', None)
        if lit_tag == 'yes':
            lighting = 1.0
        elif lit_tag == 'no':
            lighting = 0.1
        else:
            # Infer from highway type (residential/living_street usually lit)
            if highway in ['residential', 'living_street', 'pedestrian', 'primary', 'secondary']:
                lighting = 0.7
            else:
                lighting = 0.4
        
        # Walkability score: Based on highway type
        walkability = self.HIGHWAY_WALKABILITY.get(highway, 0.5)
        
        return EdgeVibeScores(
            greenery=greenery,
            blue_space=blue_space,
            quietness=quietness,
            liveliness=liveliness,
            lighting=lighting,
            walkability=walkability
        )
    
    def compute_quality_score(
        self,
        edge_scores: EdgeVibeScores,
        vibe_weights: dict[str, float]
    ) -> float:
        """
        Compute weighted quality score for an edge.
        
        Args:
            edge_scores: Individual vibe scores for the edge
            vibe_weights: User's vibe preferences
            
        Returns:
            Quality score in [0, 1]
        """
        weighted_scores = []
        total_weight = 0.0
        
        if vibe_weights.get('greenery', 0) > 0:
            w = vibe_weights['greenery']
            weighted_scores.append(edge_scores.greenery * w)
            total_weight += w
        
        if vibe_weights.get('blue_space', 0) > 0:
            w = vibe_weights['blue_space']
            weighted_scores.append(edge_scores.blue_space * w)
            total_weight += w
        
        if vibe_weights.get('introvert_mode', 0) > 0:
            w = vibe_weights['introvert_mode']
            weighted_scores.append(edge_scores.quietness * w)
            total_weight += w
        
        if vibe_weights.get('extrovert_mode', 0) > 0:
            w = vibe_weights['extrovert_mode']
            weighted_scores.append(edge_scores.liveliness * w)
            total_weight += w
        
        if vibe_weights.get('safety_check', 0) > 0:
            w = vibe_weights['safety_check']
            weighted_scores.append(edge_scores.lighting * w)
            total_weight += w
        
        if vibe_weights.get('walkability', 0) > 0:
            w = vibe_weights['walkability']
            weighted_scores.append(edge_scores.walkability * w)
            total_weight += w
        
        if total_weight == 0:
            return 0.5  # Neutral if no vibes specified
        
        return sum(weighted_scores) / total_weight
    
    def compute_generative_cost(
        self,
        base_cost: float,
        quality_score: float,
        smoothing: float = 0.6
    ) -> float:
        """
        Apply the Generative Cost Function.
        
        Formula: Cg = C_base * (1 - Quality_Score * smoothing_factor)
        
        The smoothing factor controls how much vibes influence routing.
        Higher values = stronger preference for matching vibes (may result in longer routes)
        
        Args:
            base_cost: Original edge cost (distance or time)
            quality_score: Quality score in [0, 1]
            smoothing: How much quality affects cost (0.6 = 60% max reduction/increase)
            
        Returns:
            Adjusted cost
        """
        # Cg = C_base * (1 - Quality_Score * smoothing)
        # High quality (1.0) -> cost reduced by up to 60% (making it much more attractive)
        # Low quality (0.0) -> cost unchanged (no penalty)
        # Very low quality (negative scores possible via repellents) -> cost increased up to 50%
        adjustment = 1.0 - (quality_score * smoothing)
        
        # Clamp to prevent negative costs but allow 50% cost increase for bad edges
        adjustment = max(0.4, min(1.5, adjustment))
        
        return base_cost * adjustment
    
    def create_weight_function(
        self,
        graph: nx.MultiDiGraph,
        vibe_weights: dict[str, float],
        base_weight: str = 'length'
    ):
        """
        Create a weight function for NetworkX routing.
        
        Args:
            graph: The OSM graph
            vibe_weights: User's vibe preferences
            base_weight: Base edge attribute to use ('length' or 'travel_time')
            
        Returns:
            Function suitable for nx.shortest_path weight parameter
        """
        def weight_func(u: int, v: int, data: dict) -> float:
            # Get base cost
            base_cost = data.get(base_weight, data.get('length', 100))
            
            # Get node coordinates
            u_data = graph.nodes[u]
            v_data = graph.nodes[v]
            
            # Compute vibe scores
            edge_scores = self.compute_edge_vibe_scores(
                data,
                u_data['y'], u_data['x'],
                v_data['y'], v_data['x']
            )
            
            # Compute quality score
            quality = self.compute_quality_score(edge_scores, vibe_weights)
            
            # Highway penalty: Major roads get significant penalty for nature/quietness requests
            highway = data.get('highway', 'unclassified')
            if isinstance(highway, list):
                highway = highway[0]
            
            # Check if user wants greenery or quietness
            wants_nature = vibe_weights.get('greenery', 0) > 0.5 or vibe_weights.get('introvert_mode', 0) > 0.5
            
            if wants_nature:
                # Major highways to avoid when seeking nature/quietness
                major_roads = ['motorway', 'trunk', 'primary', 'secondary']
                if highway in major_roads:
                    # Strong penalty: reduces quality score, effectively increasing cost
                    quality = quality * 0.2  # 80% penalty for highways
                elif highway in ['tertiary', 'service']:
                    # Moderate penalty for smaller roads
                    quality = quality * 0.6  # 40% penalty
            
            # Apply generative cost function
            return self.compute_generative_cost(base_cost, quality)
        
        return weight_func
