from fastapi import APIRouter, Depends, HTTPException, Request, status

from geostride.core.dependencies import get_graph_loader, get_session_store
from geostride.core.logging import get_logger
from geostride.core.session import SessionStore
from geostride.models import Coordinate, ExecuteErrorResponse, ExecuteRequest, ExecuteResponse
from geostride.services.cost_functions import CostFunctionEngine
from geostride.services.execution_service import ExecutionService
from geostride.services.graph_loader import GraphLoader
from geostride.services.loop_generator import LoopGenerator
from geostride.services.routing import RoutingService
from geostride.services.vibe_engine import VibeEngine

logger = get_logger(__name__)

router = APIRouter(tags=["Execution"])

GRAPH_SEARCH_RADIUS_METERS = 3000


def _build_execution_service(
    graph_loader: GraphLoader,
    lat: float,
    lon: float,
) -> ExecutionService:
    graph = graph_loader.load_graph_by_point(lat, lon, dist_meters=GRAPH_SEARCH_RADIUS_METERS)
    cost_engine = CostFunctionEngine(graph_loader.amenities)
    vibe_engine = VibeEngine(graph_loader.amenities)
    routing_service = RoutingService(graph, cost_engine, vibe_engine)
    loop_generator = LoopGenerator(graph, routing_service, cost_engine, vibe_engine)
    return ExecutionService(
        graph_loader, graph, cost_engine, vibe_engine, routing_service, loop_generator
    )


@router.post(
    "/execute",
    response_model=ExecuteResponse,
    responses={400: {"model": ExecuteErrorResponse}},
)
async def execute_route(
    request: ExecuteRequest,
    http_request: Request,
    graph_loader: GraphLoader = Depends(get_graph_loader),  # noqa: B008
    session_store: SessionStore = Depends(get_session_store),  # noqa: B008
) -> ExecuteResponse:
    try:
        origin = request.origin
        if origin is None and request.session_id:
            session_data = session_store.get(request.session_id, "location")
            if session_data:
                origin = Coordinate(lat=session_data["lat"], lon=session_data["lon"])
                logger.info("Retrieved location from session", session_id=request.session_id)
            else:
                raise ValueError(
                    f"Session {request.session_id} not found. Set location first."
                )

        if origin is None:
            raise ValueError("Either origin coordinates or session_id must be provided")

        execution_service = _build_execution_service(
            graph_loader, origin.lat, origin.lon
        )

        execute_request = ExecuteRequest(
            origin=origin,
            duration_minutes=request.duration_minutes,
            vibes=request.vibes,
            no_go_zones=request.no_go_zones,
        )

        result = execution_service.execute(execute_request)

        if request.session_id:
            session_store.set(request.session_id, "route", result.model_dump())
            ws_manager = http_request.app.state.ws_manager
            await ws_manager.send_route(request.session_id, result.model_dump())

        return result

    except ValueError as e:
        logger.error("Route execution failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except Exception as e:
        logger.exception("Unexpected error during route execution")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Route generation failed: {str(e)}",
        ) from e
