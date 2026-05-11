from pydantic import BaseModel, Field

class Coordinate(BaseModel):
    """A geographic coordinate point."""
    lat: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees (-90 to 90)")
    lon: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees (-180 to 180)")

class VibeWeights(BaseModel):
    """Precise vibe weights as floats from 0.0 to 1.0."""
    greenery: float = Field(default=0.5, ge=0.0, le=1.0)
    blue_space: float = Field(default=0.0, ge=0.0, le=1.0)
    introvert_mode: float = Field(default=0.0, ge=0.0, le=1.0)
    extrovert_mode: float = Field(default=0.0, ge=0.0, le=1.0)
    safety_check: float = Field(default=0.5, ge=0.0, le=1.0)
    walkability: float = Field(default=0.7, ge=0.0, le=1.0)

class NoGoZone(BaseModel):
    """A polygon area to avoid during routing."""
    vertices: list[Coordinate] = Field(..., min_length=3)

class VibeBreakdown(BaseModel):
    """Detailed vibe scores for transparency."""
    greenery: float
    blue_space: float
    quietness: float
    liveliness: float
    safety: float
    walkability: float
    overall: float

class RouteMetadata(BaseModel):
    """Route metadata for display."""
    distance_meters: float = Field(..., description="Total route distance in meters")
    estimated_duration_minutes: float = Field(..., description="Estimated walking time in minutes")
    vibe_score: float = Field(..., ge=0.0, le=1.0, description="Overall route quality based on vibes")
    vibe_breakdown: VibeBreakdown = Field(..., description="Individual vibe scores achieved")
