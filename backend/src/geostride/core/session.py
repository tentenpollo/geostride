import time
from typing import Optional, Dict, Any

class SessionStore:
    """In-memory session store with TTL."""
    def __init__(self, ttl_seconds: int = 3600):
        self.ttl_seconds = ttl_seconds
        self._sessions: Dict[str, Dict[str, Any]] = {}
    
    def _cleanup(self):
        """Remove expired sessions."""
        now = time.time()
        expired = [sid for sid, data in self._sessions.items() if now - data.get('timestamp', 0) > self.ttl_seconds]
        for sid in expired:
            del self._sessions[sid]
            
    def set(self, session_id: str, key: str, value: Any):
        self._cleanup()
        if session_id not in self._sessions:
            self._sessions[session_id] = {'timestamp': time.time()}
        self._sessions[session_id][key] = value
        self._sessions[session_id]['timestamp'] = time.time()
        
    def get(self, session_id: str, key: str) -> Optional[Any]:
        self._cleanup()
        session = self._sessions.get(session_id)
        if session:
            session['timestamp'] = time.time()
            return session.get(key)
        return None
