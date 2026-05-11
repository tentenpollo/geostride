"""
Vibe Engine

Implements the Magnet and Repellent system for route scoring.
Magnets attract routes toward desirable features.
Repellents push routes away from undesirable features.
"""
from dataclasses import dataclass, field
from typing import Optional
import math

from geostride.utils.geo import haversine_distance


@dataclass
class Magnet:
    """An attractor that reduces cost for nearby edges."""
    name: str
    lat: float
    lon: float
    strength: float = 1.0  # How strongly it attracts (0-1)
    radius_meters: float = 100  # Effective radius
    vibe_type: str = "generic"  # Which vibe this magnet supports


@dataclass
class Repellent:
    """A detractor that increases cost for nearby edges."""
    name: str
    lat: float
    lon: float
    strength: float = 1.0  # How strongly it repels (0-1)
    radius_meters: float = 100  # Effective radius
    vibe_type: str = "generic"  # Which vibe this repellent opposes


@dataclass
class VibeProfile:
    """Computed vibe profile for a route segment or entire route."""
    greenery: float = 0.0
    blue_space: float = 0.0
    quietness: float = 0.0
    liveliness: float = 0.0
    safety: float = 0.0
    walkability: float = 0.0
    overall: float = 0.0
    
    def to_dict(self) -> dict[str, float]:
        return {
            "greenery": round(self.greenery, 3),
            "blue_space": round(self.blue_space, 3),
            "quietness": round(self.quietness, 3),
            "liveliness": round(self.liveliness, 3),
            "safety": round(self.safety, 3),
            "walkability": round(self.walkability, 3),
            "overall": round(self.overall, 3)
        }


class VibeEngine:
    """
    Engine for computing route vibes using Magnets and Repellents.
    
    Magnets (attractors):
    - Parks, gardens -> greenery
    - Rivers, lakes, coastline -> blue_space
    - Quiet residential streets -> introvert_mode
    - Shops, cafes, bars -> extrovert_mode
    - Lit streets -> safety
    - Footways, pedestrian zones -> walkability
    
    Repellents (detractors):
    - Industrial areas -> greenery (negative)
    - Highways, trunk roads -> quietness (negative)
    - Unlit streets -> safety (negative)
    - Non-pedestrian roads -> walkability (negative)
    """
    
    def __init__(self, amenities: dict):
        """
        Initialize with amenity data.
        
        Args:
            amenities: Dict with 'parks', 'water', 'shops', 'food' keys
        """
        self.amenities = amenities
        self.magnets: list[Magnet] = []
        self.repellents: list[Repellent] = []
        self._build_magnets_and_repellents()
    
    def _build_magnets_and_repellents(self) -> None:
        """Build magnets from amenity data."""
        # Parks -> Greenery magnets
        for park in self.amenities.get('parks', []):
            self.magnets.append(Magnet(
                name="park",
                lat=park['lat'],
                lon=park['lon'],
                strength=0.9,
                radius_meters=150,
                vibe_type="greenery"
            ))
        
        # Water -> Blue space magnets
        for water in self.amenities.get('water', []):
            self.magnets.append(Magnet(
                name="water",
                lat=water['lat'],
                lon=water['lon'],
                strength=0.85,
                radius_meters=200,
                vibe_type="blue_space"
            ))
        
        # Shops -> Liveliness magnets
        for shop in self.amenities.get('shops', []):
            self.magnets.append(Magnet(
                name="shop",
                lat=shop['lat'],
                lon=shop['lon'],
                strength=0.6,
                radius_meters=50,
                vibe_type="liveliness"
            ))
        
        # Food venues -> Liveliness magnets (stronger)
        for food in self.amenities.get('food', []):
            self.magnets.append(Magnet(
                name="food",
                lat=food['lat'],
                lon=food['lon'],
                strength=0.75,
                radius_meters=75,
                vibe_type="liveliness"
            ))
    
    def add_custom_magnet(self, magnet: Magnet) -> None:
        """Add a custom magnet."""
        self.magnets.append(magnet)
    
    def add_custom_repellent(self, repellent: Repellent) -> None:
        """Add a custom repellent."""
        self.repellents.append(repellent)
    
    def add_no_go_zone(
        self,
        center_lat: float,
        center_lon: float,
        radius_meters: float = 200
    ) -> None:
        """Add a no-go zone as a strong repellent."""
        self.repellents.append(Repellent(
            name="no_go_zone",
            lat=center_lat,
            lon=center_lon,
            strength=1.0,  # Maximum repulsion
            radius_meters=radius_meters,
            vibe_type="all"  # Affects all vibes
        ))
    

    
    def compute_magnet_influence(
        self,
        lat: float, lon: float,
        vibe_type: str
    ) -> float:
        """
        Compute total magnet influence at a point for a vibe type.
        
        Returns:
            Influence score in [0, 1]
        """
        total_influence = 0.0
        
        for magnet in self.magnets:
            if magnet.vibe_type != vibe_type:
                continue
            
            dist = haversine_distance(lat, lon, magnet.lat, magnet.lon)
            
            if dist <= magnet.radius_meters:
                # Linear decay from center
                decay = 1.0 - (dist / magnet.radius_meters)
                influence = magnet.strength * decay
                total_influence = max(total_influence, influence)
        
        return min(1.0, total_influence)
    
    def compute_repellent_influence(
        self,
        lat: float, lon: float,
        vibe_type: str
    ) -> float:
        """
        Compute total repellent influence at a point.
        
        Returns:
            Penalty factor (higher = more penalty)
        """
        max_penalty = 0.0
        
        for repellent in self.repellents:
            if repellent.vibe_type not in (vibe_type, "all"):
                continue
            
            dist = haversine_distance(lat, lon, repellent.lat, repellent.lon)
            
            if dist <= repellent.radius_meters:
                decay = 1.0 - (dist / repellent.radius_meters)
                penalty = repellent.strength * decay
                max_penalty = max(max_penalty, penalty)
        
        return max_penalty
    
    def compute_point_vibe_profile(
        self,
        lat: float, lon: float,
        edge_data: Optional[dict] = None
    ) -> VibeProfile:
        """
        Compute full vibe profile for a point.
        
        Args:
            lat, lon: Point coordinates
            edge_data: Optional edge attributes for walkability/safety inference
            
        Returns:
            VibeProfile with all vibe scores
        """
        profile = VibeProfile()
        
        # Greenery from park magnets
        profile.greenery = self.compute_magnet_influence(lat, lon, "greenery")
        
        # Blue space from water magnets
        profile.blue_space = self.compute_magnet_influence(lat, lon, "blue_space")
        
        # Liveliness from shop/food magnets
        profile.liveliness = self.compute_magnet_influence(lat, lon, "liveliness")
        
        # Quietness is inverse of liveliness (simplified)
        profile.quietness = max(0, 1.0 - profile.liveliness * 0.7)
        
        # Safety and walkability from edge data if available
        if edge_data:
            highway = edge_data.get('highway', 'unclassified')
            if isinstance(highway, list):
                highway = highway[0]
            
            # Safety from lighting
            lit = edge_data.get('lit', None)
            if lit == 'yes':
                profile.safety = 0.95
            elif lit == 'no':
                profile.safety = 0.2
            elif highway in ['residential', 'living_street', 'pedestrian']:
                profile.safety = 0.7
            else:
                profile.safety = 0.5
            
            # Walkability from highway type
            walkable_highways = {
                'footway': 1.0, 'pedestrian': 0.95, 'path': 0.9,
                'living_street': 0.85, 'residential': 0.75
            }
            profile.walkability = walkable_highways.get(highway, 0.4)
        else:
            profile.safety = 0.5
            profile.walkability = 0.5
        
        # Apply repellent penalties
        for vibe in ['greenery', 'blue_space', 'quietness', 'liveliness', 'safety', 'walkability']:
            penalty = self.compute_repellent_influence(lat, lon, vibe)
            current = getattr(profile, vibe)
            setattr(profile, vibe, max(0, current - penalty))
        
        # Compute overall score
        scores = [
            profile.greenery, profile.blue_space, profile.quietness,
            profile.liveliness, profile.safety, profile.walkability
        ]
        profile.overall = sum(scores) / len(scores)
        
        return profile
    
    def compute_route_vibe_profile(
        self,
        route_coords: list[tuple[float, float]],
        edge_data_list: Optional[list[dict]] = None
    ) -> VibeProfile:
        """
        Compute aggregate vibe profile for an entire route.
        
        Args:
            route_coords: List of (lat, lon) tuples
            edge_data_list: Optional list of edge attributes
            
        Returns:
            Aggregated VibeProfile
        """
        if not route_coords:
            return VibeProfile()
        
        profiles = []
        for i, (lat, lon) in enumerate(route_coords):
            edge_data = edge_data_list[i] if edge_data_list and i < len(edge_data_list) else None
            profiles.append(self.compute_point_vibe_profile(lat, lon, edge_data))
        
        # Average all profiles
        avg_profile = VibeProfile()
        n = len(profiles)
        
        avg_profile.greenery = sum(p.greenery for p in profiles) / n
        avg_profile.blue_space = sum(p.blue_space for p in profiles) / n
        avg_profile.quietness = sum(p.quietness for p in profiles) / n
        avg_profile.liveliness = sum(p.liveliness for p in profiles) / n
        avg_profile.safety = sum(p.safety for p in profiles) / n
        avg_profile.walkability = sum(p.walkability for p in profiles) / n
        avg_profile.overall = sum(p.overall for p in profiles) / n
        
        return avg_profile
    
    def generate_transparency_summary(
        self,
        vibe_profile: VibeProfile,
        requested_vibes: dict[str, float]
    ) -> str:
        """
        Generate a human-readable summary of how well the route matches vibes.
        
        This helps "demystify" the routing decision.
        """
        summary_parts = []
        
        vibe_mapping = {
            'greenery': ('greenery', 'nature and green spaces'),
            'blue_space': ('blue_space', 'water features'),
            'introvert_mode': ('quietness', 'peaceful, quiet areas'),
            'extrovert_mode': ('liveliness', 'bustling, lively areas'),
            'safety_check': ('safety', 'well-lit, safe streets'),
            'walkability': ('walkability', 'pedestrian-friendly paths'),
        }
        
        for req_vibe, (profile_attr, description) in vibe_mapping.items():
            weight = requested_vibes.get(req_vibe, 0)
            if weight >= 0.5:
                score = getattr(vibe_profile, profile_attr)
                if score >= 0.7:
                    summary_parts.append(f"Excellent {description} ({score:.0%} match)")
                elif score >= 0.5:
                    summary_parts.append(f"Good {description} ({score:.0%} match)")
                else:
                    summary_parts.append(f"Limited {description} available ({score:.0%} match)")
        
        if not summary_parts:
            return "This route provides a balanced walking experience."
        
        return "This route features: " + "; ".join(summary_parts) + "."
