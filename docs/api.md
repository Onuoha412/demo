# API

## Health

`GET /api/health` returns the service status.

## Queue updates

`WS /ws/queues/{queue_id}` accepts a WebSocket connection and sends an initial
connection event. Queue update events will be added behind this stable stream.
