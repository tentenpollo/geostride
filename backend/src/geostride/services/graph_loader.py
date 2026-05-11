"""
OSM Graph Loader Service

Handles downloading, caching, and loading OpenStreetMap walking networks
using OSMnx. Includes amenity data enrichment for vibe scoring.
"""
import hashlib
import json
import math
import time
from pathlib import Path

import networkx as nx
import osmnx as ox

from geostride.core.logging import get_logger

logger = get_logger(__name__)


class GraphLoader:
    """
    Manages OSM graph loading and caching.
    
    Uses OSMnx to download walk networks and nearby amenities.
    Caches graphs to disk to avoid repeated API calls.
    """
    
    def __init__(self, cache_dir: Path, ttl_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_hours * 3600
        self._graph: nx.MultiDiGraph | None = None
        self._amenities: dict = {}
        self._current_region: str | None = None
        
        # Configure OSMnx
        ox.settings.use_cache = True
        ox.settings.cache_folder = str(self.cache_dir / "osmnx_cache")
        ox.settings.log_console = False
    
    def _get_cache_key(self, place: str) -> str:
        """Generate a cache key for a place name."""
        return hashlib.md5(place.lower().encode()).hexdigest()[:12]
    
    def _get_cache_key_coords(self, lat: float, lon: float, dist: int) -> str:
        """Generate a cache key for coordinate-based queries."""
        key_str = f"{lat:.4f}_{lon:.4f}_{dist}"
        return hashlib.md5(key_str.encode()).hexdigest()[:12]
    
    def load_graph_by_place(self, place: str, network_type: str = "walk") -> nx.MultiDiGraph:
        """
        Load walking network for a named place.
        
        Args:
            place: Place name (e.g., "Manhattan, New York, USA")
            network_type: OSM network type (walk, bike, drive, all)
            
        Returns:
            NetworkX MultiDiGraph with node/edge attributes
        """
        cache_key = self._get_cache_key(place)
        cache_file = self.cache_dir / f"graph_{cache_key}.graphml"
        
        if cache_file.exists() and time.time() - cache_file.stat().st_mtime < self.ttl_seconds:
            logger.info(f"Loading cached graph for {place}")
            self._graph = ox.load_graphml(cache_file)
            self._current_region = place
        else:
            logger.info(f"Downloading graph for {place} from OSM...")
            self._graph = ox.graph_from_place(
                place,
                network_type=network_type,
                simplify=False  # Keep full geometry for accurate route rendering
            )
            # Add edge speeds and travel times for walking
            self._graph = ox.add_edge_speeds(self._graph, fallback=4.5)  # 4.5 km/h walk
            self._graph = ox.add_edge_travel_times(self._graph)
            
            # Save to cache
            ox.save_graphml(self._graph, cache_file)
            self._current_region = place
            logger.info(f"Graph cached to {cache_file}")
        
        # Load amenities for this region
        self._load_amenities_for_region(place)
        
        return self._graph
    
    def load_graph_by_point(
        self,
        lat: float,
        lon: float,
        dist_meters: int = 2000,
        network_type: str = "walk"
    ) -> nx.MultiDiGraph:
        """
        Load walking network around a point.
        
        Args:
            lat: Center latitude
            lon: Center longitude
            dist_meters: Radius in meters
            network_type: OSM network type
            
        Returns:
            NetworkX MultiDiGraph
        """
        cache_key = self._get_cache_key_coords(lat, lon, dist_meters)
        cache_file = self.cache_dir / f"graph_{cache_key}.graphml"
        
        if cache_file.exists() and time.time() - cache_file.stat().st_mtime < self.ttl_seconds:
            logger.info(f"Loading cached graph for ({lat}, {lon})")
            self._graph = ox.load_graphml(cache_file)
        else:
            logger.info(f"Downloading graph around ({lat}, {lon})...")
            self._graph = ox.graph_from_point(
                (lat, lon),
                dist=dist_meters,
                network_type=network_type,
                simplify=False  # Keep full geometry for accurate route rendering
            )
            self._graph = ox.add_edge_speeds(self._graph, fallback=4.5)
            self._graph = ox.add_edge_travel_times(self._graph)
            
            ox.save_graphml(self._graph, cache_file)
            logger.info(f"Graph cached to {cache_file}")
        
        self._current_region = f"point_{cache_key}"
        self._load_amenities_for_point(lat, lon, dist_meters)
        
        return self._graph
    
    def _load_amenities_for_region(self, place: str) -> None:
        """Load POI/amenity data for vibe scoring."""
        cache_key = self._get_cache_key(place)
        amenity_cache = self.cache_dir / f"amenities_{cache_key}.json"
        
        if (
            amenity_cache.exists()
            and time.time() - amenity_cache.stat().st_mtime < self.ttl_seconds
        ):
            with open(amenity_cache) as f:
                self._amenities = json.load(f)
            logger.info(f"Loaded cached amenities for {place}")
            return
        
        logger.info(f"Downloading amenities for {place}...")
        self._amenities = self._fetch_amenities_by_place(place)
        
        with open(amenity_cache, 'w') as f:
            json.dump(self._amenities, f)
    
    def _load_amenities_for_point(self, lat: float, lon: float, dist: int) -> None:
        """Load POI/amenity data around a point."""
        cache_key = self._get_cache_key_coords(lat, lon, dist)
        amenity_cache = self.cache_dir / f"amenities_{cache_key}.json"
        
        if (
            amenity_cache.exists()
            and time.time() - amenity_cache.stat().st_mtime < self.ttl_seconds
        ):
            with open(amenity_cache) as f:
                self._amenities = json.load(f)
            return
        
        self._amenities = self._fetch_amenities_by_point(lat, lon, dist)
        
        with open(amenity_cache, 'w') as f:
            json.dump(self._amenities, f)
    
    def _fetch_amenities_by_place(self, place: str) -> dict:
        """Fetch amenities from OSM for a named place."""
        amenities = {
            "parks": [],
            "water": [],
            "shops": [],
            "food": [],
            "lit_streets": []
        }
        
        try:
            # Parks and green spaces
            tags = {"leisure": ["park", "garden", "nature_reserve"], "landuse": "grass"}
            parks = ox.features_from_place(place, tags)
            if not parks.empty:
                amenities["parks"] = [
                    {"lat": geom.centroid.y, "lon": geom.centroid.x}
                    for geom in parks.geometry if geom is not None
                ]
        except Exception as e:
            logger.warning(f"Could not fetch parks: {e}")
        
        try:
            # Water bodies
            tags = {"natural": "water", "waterway": True}
            water = ox.features_from_place(place, tags)
            if not water.empty:
                amenities["water"] = [
                    {"lat": geom.centroid.y, "lon": geom.centroid.x}
                    for geom in water.geometry if geom is not None
                ]
        except Exception as e:
            logger.warning(f"Could not fetch water: {e}")
        
        try:
            # Commercial areas
            tags = {"shop": True}
            shops = ox.features_from_place(place, tags)
            if not shops.empty:
                amenities["shops"] = [
                    {"lat": geom.centroid.y, "lon": geom.centroid.x}
                    for geom in shops.geometry[:500] if geom is not None  # Limit
                ]
        except Exception as e:
            logger.warning(f"Could not fetch shops: {e}")
        
        try:
            # Food/entertainment
            tags = {"amenity": ["restaurant", "cafe", "bar", "pub"]}
            food = ox.features_from_place(place, tags)
            if not food.empty:
                amenities["food"] = [
                    {"lat": geom.centroid.y, "lon": geom.centroid.x}
                    for geom in food.geometry[:500] if geom is not None
                ]
        except Exception as e:
            logger.warning(f"Could not fetch food venues: {e}")
        
        return amenities
    
    def _fetch_amenities_by_point(self, lat: float, lon: float, dist: int) -> dict:
        """Fetch amenities around a point."""
        amenities = {
            "parks": [],
            "water": [],
            "shops": [],
            "food": [],
            "lit_streets": []
        }
        
        try:
            tags = {"leisure": ["park", "garden"], "landuse": "grass"}
            parks = ox.features_from_point((lat, lon), tags, dist=dist)
            if not parks.empty:
                amenities["parks"] = [
                    {"lat": geom.centroid.y, "lon": geom.centroid.x}
                    for geom in parks.geometry if geom is not None
                ]
        except Exception as e:
            logger.warning(f"Could not fetch parks: {e}")
        
        try:
            tags = {"natural": "water"}
            water = ox.features_from_point((lat, lon), tags, dist=dist)
            if not water.empty:
                amenities["water"] = [
                    {"lat": geom.centroid.y, "lon": geom.centroid.x}
                    for geom in water.geometry if geom is not None
                ]
        except Exception as e:
            logger.warning(f"Could not fetch water: {e}")
        
        try:
            tags = {"shop": True}
            shops = ox.features_from_point((lat, lon), tags, dist=dist)
            if not shops.empty:
                amenities["shops"] = [
                    {"lat": geom.centroid.y, "lon": geom.centroid.x}
                    for geom in shops.geometry[:200] if geom is not None
                ]
        except Exception as e:
            logger.warning(f"Could not fetch shops: {e}")
        
        try:
            tags = {"amenity": ["restaurant", "cafe", "bar"]}
            food = ox.features_from_point((lat, lon), tags, dist=dist)
            if not food.empty:
                amenities["food"] = [
                    {"lat": geom.centroid.y, "lon": geom.centroid.x}
                    for geom in food.geometry[:200] if geom is not None
                ]
        except Exception as e:
            logger.warning(f"Could not fetch food: {e}")
        
        return amenities
    
    @property
    def graph(self) -> nx.MultiDiGraph | None:
        """Get the currently loaded graph."""
        return self._graph
    
    @property
    def amenities(self) -> dict:
        """Get the amenities for the current region."""
        return self._amenities
    
    def get_nearest_node(self, lat: float, lon: float) -> int:
        """Find the nearest graph node to a coordinate."""
        if self._graph is None:
            raise ValueError("No graph loaded. Call load_graph_* first.")
        return ox.nearest_nodes(self._graph, lon, lat)
    
    def get_node_coords(self, node_id: int) -> tuple[float, float]:
        """Get coordinates for a node."""
        if self._graph is None:
            raise ValueError("No graph loaded.")
        node_data = self._graph.nodes[node_id]
        return (node_data['y'], node_data['x'])  # lat, lon
    
    def is_point_in_graph_bounds(self, lat: float, lon: float, buffer_meters: float = 500) -> bool:
        """
        Check if a point is within the loaded graph's bounds with a buffer.
        
        Args:
            lat, lon: Point coordinates
            buffer_meters: How far outside the bounds is still considered "in" (default 500m)
            
        Returns:
            True if point is within bounds + buffer
        """
        if self._graph is None:
            return False
        
        try:
            # Get graph bounds
            nodes = self._graph.nodes(data=True)
            lats = [data['y'] for _, data in nodes]
            lons = [data['x'] for _, data in nodes]
            
            if not lats or not lons:
                return False
            
            min_lat, max_lat = min(lats), max(lats)
            min_lon, max_lon = min(lons), max(lons)
            
            # Convert buffer to degrees (approximate)
            buffer_lat = buffer_meters / 111000  # ~111km per degree
            buffer_lon = buffer_meters / (111000 * abs(math.cos(math.radians(lat))))
            
            # Check if point is within bounds + buffer
            return (min_lat - buffer_lat <= lat <= max_lat + buffer_lat and
                    min_lon - buffer_lon <= lon <= max_lon + buffer_lon)
        except Exception as e:
            logger.warning(f"Could not check graph bounds: {e}")
            return False
    
    def list_cached_regions(self) -> list[str]:
        """List all cached graph files."""
        return [f.stem.replace("graph_", "") for f in self.cache_dir.glob("graph_*.graphml")]
