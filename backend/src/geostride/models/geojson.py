from typing import Any

from pydantic import BaseModel, Field


class GeoJSONGeometry(BaseModel):
    """GeoJSON geometry object."""
    type: str = Field(default="LineString")
    coordinates: list[list[float]] = Field(
        ...,
        description="Array of [longitude, latitude] coordinate pairs"
    )

class GeoJSONFeature(BaseModel):
    """GeoJSON feature object."""
    type: str = Field(default="Feature")
    geometry: GeoJSONGeometry
    properties: dict[str, Any] = Field(default_factory=dict)

class GeoJSONFeatureCollection(BaseModel):
    """GeoJSON FeatureCollection for map rendering."""
    type: str = Field(default="FeatureCollection")
    features: list[GeoJSONFeature]
