# Future Improvements

Items deferred from the initial restructuring for future pull requests.

## WebSocket Client in Frontend
The backend has a working WebSocket endpoint (`/ws/{session_id}`) that pushes route data
in real time. The frontend currently polls via REST `POST /execute`. Connecting a
`useWebSocket` hook would enable progress updates during long route generations.

## Component Decomposition
`App.tsx` is ~290 lines in a single file. Splitting into `MapView`, `Sidebar`, and
`VibeSliders` components would improve maintainability and testability.

## Keyboard Shortcuts
- `Enter` on the map to confirm pin location and trigger route generation
- `Escape` to clear the pinned location

## LLM Integration Layer
Backend config has LLM provider settings (`LLM_PROVIDER`, `LLM_MODEL`, etc.) as stubs.
Implement a pluggable `LLMProvider` interface with concrete backends (OpenAI, Anthropic,
local/ollama) and a `POST /parse-nl` endpoint that converts natural language descriptions
to vibe weights and duration. Add a text input to the frontend above the vibe sliders.

## Caching TTL for OSM Downloads
The graph loader already has an MD5-based cache key system and a `ttl_hours` parameter.
Expose `CACHE_TTL_HOURS` as an environment variable for configurable cache expiry.

## Production Deployment
- Restrict CORS origins for production
- Add authentication (API keys) for public endpoints
- Production Dockerfile with multi-stage builds
