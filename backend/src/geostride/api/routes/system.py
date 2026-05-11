from fastapi import APIRouter, Depends
from geostride.models import HealthResponse
from geostride.core.dependencies import get_graph_loader
from geostride.services.graph_loader import GraphLoader
import httpx

router = APIRouter(tags=["System"])

@router.get("/health", response_model=HealthResponse)
async def health_check(graph_loader: GraphLoader = Depends(get_graph_loader)):
    """Check API health and graph status."""
    
    # Check OSM Connectivity
    osm_connected = False
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get("https://nominatim.openstreetmap.org/status.php?format=json")
            if response.status_code == 200:
                osm_connected = True
    except Exception:
        pass
        
    return HealthResponse(
        status="healthy" if osm_connected else "degraded (OSM unreachable)",
        version="1.0.0",
        graph_loaded=graph_loader is not None and graph_loader.graph is not None,
        cached_regions=graph_loader.list_cached_regions() if graph_loader else []
    )

@router.get("/cached-regions")
async def list_cached_regions(graph_loader: GraphLoader = Depends(get_graph_loader)):
    """List all cached graph regions."""
    if graph_loader is None:
        return {"regions": []}
    return {"regions": graph_loader.list_cached_regions()}
