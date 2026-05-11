from fastapi import APIRouter, Depends, HTTPException

from geostride.core.dependencies import get_session_store
from geostride.core.logging import get_logger
from geostride.core.session import SessionStore

logger = get_logger(__name__)

router = APIRouter(tags=["Session Management"])

@router.post("/set-location")
async def set_location(request: dict, session_store: SessionStore = Depends(get_session_store)):  # noqa: B008
    """Store location in session."""
    session_id = request.get("session_id")
    lat = request.get("lat")
    lon = request.get("lon")
    
    if not session_id or lat is None or lon is None:
        raise HTTPException(
            status_code=400,
            detail="Missing required fields: session_id, lat, lon"
        )
    
    session_store.set(session_id, "location", {"lat": lat, "lon": lon})
    logger.info("Location stored", session_id=session_id, lat=lat, lon=lon)
    return {"success": True, "message": "Location stored"}

@router.get("/get-route/{session_id}")
async def get_route(session_id: str, session_store: SessionStore = Depends(get_session_store)):  # noqa: B008
    """Retrieve a generated route by session ID."""
    route_data = session_store.get(session_id, "route")
    if route_data:
        return route_data
    raise HTTPException(
        status_code=404,
        detail="No route found for this session."
    )
