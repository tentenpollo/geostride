
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from geostride.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Session Management"])

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info("WebSocket connected", session_id=session_id)

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info("WebSocket disconnected", session_id=session_id)

    async def send_route(self, session_id: str, route_data: dict):
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_json({
                    "type": "route_ready",
                    "data": route_data
                })
                logger.info("Route sent via WebSocket", session_id=session_id)
            except Exception as e:
                logger.error(
                    "Failed to send route via WebSocket",
                    error=str(e), session_id=session_id
                )


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.app.state.ws_manager.connect(websocket, session_id)
    try:
        while True:
            _data = await websocket.receive_text()
    except WebSocketDisconnect:
        websocket.app.state.ws_manager.disconnect(session_id)
