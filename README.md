# QueueLess

QueueLess is a digital queue-management platform with customer, staff, and
administration workflows, real-time queue updates, wait-time estimates, QR
joining, and internal notifications.

- `frontend/` — React, TypeScript, and Vite client
- `backend/` — FastAPI API, SQLAlchemy database abstraction, and auth boundaries
- `ai/` — wait-time prediction features and models
- `database/` — PostgreSQL schema, migrations, and seeds
- `e2e/` — customer, staff, and admin end-to-end tests
- `docs/` — architecture, API, database, and deployment notes

## Local development

Install frontend dependencies:

```bash
npm install --prefix frontend
```

### Staff application

Staff accounts must have `role = 'staff'` and a `branch_id` assigned before they
can access the staff application. Open `/staff/login` after starting the
frontend. Staff queue mutations are authenticated and restricted to the
assigned branch; customers receive `403` responses for staff operations.

### Admin application

Administrators use `/admin/login`. Admin routes are protected by the FastAPI
`require_admin` dependency; frontend route protection is only an additional UX
guard. The admin console provides paginated organization, branch, service,
counter, queue, and user management plus analytics at `/admin/analytics`.

### Real-time queue updates

Queue updates are delivered through `ws://localhost:8000/ws/queues/{queue_id}`.
Customer, staff, and public display clients reconnect automatically with
exponential backoff. Set `REDIS_URL` to an Upstash Redis URL for cross-process
pub/sub; Redis is best-effort and PostgreSQL remains the durable source of
truth. The public display route is `/display/{queue_id}`.

### Wait-time estimation

The first wait-time engine is a deterministic statistical estimation model, not
a trained machine-learning or external AI service. It combines the people
ahead, configured service duration, available counters, and completed service
history. Predictions include a range, confidence score, model version, and
factor explanation. The replaceable model boundary is under `backend/app/ai/`.

### QR joining and notifications

Service pages expose QR codes that contain only public QueueLess join URLs:
`/join/{service_id}` or `/join/{branch_id}/{service_id}`. They do not contain
credentials, database URLs, or customer information. Authenticated customers
can view `/notifications`, mark notifications read, and configure preferences.
Notifications are durable PostgreSQL records with event-key idempotency.
Browser notifications are optional and never required for queue operation; if
permission is denied, in-app notifications continue to work. SMS is not
required.

Start the backend (Linux/macOS):

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Start the frontend in a second terminal:

```bash
npm run dev --prefix frontend
```

The frontend proxies API requests to `VITE_API_URL` (default
`http://localhost:8000`). Copy [frontend/.env.example](frontend/.env.example)
and [backend/.env.example](backend/.env.example) to `.env` files as needed.
Before starting the backend, set `JWT_SECRET_KEY` to a unique random value with
at least 32 bytes, for example `openssl rand -hex 32`. An empty, known
placeholder, or weak value causes the backend to fail closed at startup.

## Verification

```bash
npm run build --prefix frontend
cd backend && pytest -q
```

The backend exposes `GET /health` and `GET /api/v1/health`.

## Core queue engine

The current queue API supports joining, position lookup, pagination, calling,
starting, completing, skipping, and cancelling entries:

```text
POST /api/v1/queues/{queue_id}/join
GET  /api/v1/queues/{queue_id}
GET  /api/v1/queues/{queue_id}/position/{entry_id}
POST /api/v1/queues/{queue_id}/next
POST /api/v1/queue-entries/{entry_id}/call
POST /api/v1/queue-entries/{entry_id}/start
POST /api/v1/queue-entries/{entry_id}/complete
POST /api/v1/queue-entries/{entry_id}/skip
POST /api/v1/queue-entries/{entry_id}/cancel
```

Queue numbers are allocated under a row lock and are monotonically increasing
for the lifetime of a queue. See [docs/queue-engine.md](docs/queue-engine.md)
for state transitions and wait-time calculation.

## Database migrations

From the repository root, start PostgreSQL with `docker compose up -d
postgres`, then run migrations from the backend directory:

```bash
cd backend
alembic upgrade head
```

Demo records can be loaded after migration with:

```bash
psql "$DATABASE_URL" -f ../database/seeds/demo_data.sql
```
