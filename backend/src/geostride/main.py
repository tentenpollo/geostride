from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from geostride.core.config import get_settings
from geostride.core.logging import configure_logging, get_logger
from geostride.core.session import SessionStore
from geostride.services.graph_loader import GraphLoader
from geostride.models import ErrorResponse
from geostride.api.routes import system, session, execute, websocket
from geostride.api.routes.websocket import ConnectionManager

settings = get_settings()
configure_logging(debug=settings.debug)
logger = get_logger(__name__)

limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting GeoStride...")

    app.state.session_store = SessionStore(ttl_seconds=settings.session_ttl_seconds)
    app.state.graph_loader = GraphLoader(settings.cache_dir)
    app.state.ws_manager = ConnectionManager()

    yield

    logger.info("Shutting down GeoStride...")

app = FastAPI(
    title="GeoStride API",
    description="Generative Walking Route Planner API",
    version="1.0.0",
    lifespan=lifespan,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    }
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router)
app.include_router(session.router)
app.include_router(execute.router)
app.include_router(websocket.router)

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            success=False,
            error=exc.detail,
            error_code=f"HTTP_{exc.status_code}"
        ).model_dump()
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "geostride.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
