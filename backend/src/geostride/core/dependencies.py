from fastapi import Request
from geostride.core.session import SessionStore
from geostride.services.graph_loader import GraphLoader

def get_session_store(request: Request) -> SessionStore:
    return request.app.state.session_store

def get_graph_loader(request: Request) -> GraphLoader:
    return request.app.state.graph_loader
