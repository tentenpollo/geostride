
from pydantic import BaseModel, Field

from .core import Coordinate, NoGoZone, RouteMetadata, VibeWeights
from .geojson import GeoJSONFeatureCollection


class ExecuteRequest(BaseModel):
    """Execution request."""
    origin: Coordinate | None = Field(default=None)
    session_id: str | None = Field(default=None)
    duration_minutes: int = Field(default=30, ge=5, le=180)
    vibes: VibeWeights = Field(default_factory=VibeWeights)
    no_go_zones: list[NoGoZone] = Field(default_factory=list)

class ExecutionDetails(BaseModel):
    """Technical execution details."""
    algorithm: str = Field(default="dijkstra")
    nodes_explored: int = Field(...)
    graph_size: str = Field(...)
    disjoint_percentage: float = Field(...)
    execution_time_ms: float = Field(...)

class ExecuteResponse(BaseModel):
    """Execution response."""
    success: bool = Field(default=True)
    geojson: GeoJSONFeatureCollection
    metadata: RouteMetadata
    execution_details: ExecutionDetails

class ErrorResponse(BaseModel):
    """Standard error response."""
    success: bool = Field(default=False)
    error: str
    error_code: str

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    graph_loaded: bool
    cached_regions: list[str]
