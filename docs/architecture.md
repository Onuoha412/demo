# Architecture

QueueLess is a monorepo with a Vite client, FastAPI application layer, SQLite
persistence, process-local WebSocket updates, and a separately versioned
AI wait-time engine. GitHub Pages serves the static frontend, while a
single-instance FastAPI service owns the persistent SQLite database.

The frontend communicates with the API through `/api` and queue streams through
`/ws/queues/{queue_id}`. Production uses HTTPS, WSS, and revocable bearer
sessions, so cross-origin requests do not depend on third-party cookies. In
local development Vite proxies both paths to the FastAPI service.
