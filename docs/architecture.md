# Architecture

QueueLess is a monorepo with a Vite client, FastAPI application layer,
PostgreSQL/Supabase persistence, Redis/Upstash transient state, WebSocket
updates, and a separately versioned AI wait-time engine.

The frontend communicates with the API through `/api` and queue streams through
`/ws/queues/{queue_id}`. In local development Vite proxies both paths to the
FastAPI service.
