# QueueLess

QueueLess is a real-time queue-management application for customers, staff, and
administrators. The customer flow is **JOIN → WAIT → REAL-TIME POSITION →
CALL → SERVE → COMPLETE**. Queue changes and notifications are persisted by
the API; WebSockets deliver live updates, and clients can refetch state after
reconnecting.

## Architecture

- `frontend/` — React, TypeScript, and Vite single-page application.
- `backend/` — FastAPI API, authentication/authorization, SQLAlchemy models,
  queue services, notifications, and WebSockets.
- `backend/alembic/` — database migrations.
- `docs/` — database, deployment, queue, and operations guidance.
- `e2e/` — browser journeys.

GitHub Pages hosts the static frontend, and a separate FastAPI service owns
the persistent SQLite database. Cross-origin API calls use tab-scoped,
revocable opaque bearer sessions rather than depending on third-party cookies.
Production requires a persistent disk and one backend process/instance;
SQLite files and process-local real-time delivery must not be shared across
replicas.

The frontend keeps the home page and core runtime small, loads other pages and
optional monitoring on demand, and compresses/caches production assets. A
three-second first-load target is a measurable goal, not a guarantee: browser
device, network, Render startup, database activity, and user-specific API
responses all affect actual timing.

## Local development

Requirements: Python 3.12+, Node.js 22+, and npm.

Start the API:

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=sqlite:///./queueless.db
export SECRET_KEY="$(openssl rand -hex 32)"
export JWT_SECRET="$(openssl rand -hex 32)"
python -m app.db.init_db
python -m app.cli create-admin
uvicorn app.main:app --reload --port 8000
```

The one-time admin command prompts for a name, email, and password and stores
the account in the configured SQLite database. Run it in the backend's
deployment shell after migrations to provision the first administrator; it
does not add demo users or expose admin registration in the public API.

Start the frontend in another terminal:

```sh
npm install --prefix frontend
npm run dev --prefix frontend
```

The local frontend proxies API requests to `http://localhost:8000`. The
backend accepts either `JWT_SECRET` or `JWT_SECRET_KEY`; `SECRET_KEY` and the
JWT key must be distinct, unique random values of at least 32 bytes. Never use
development secrets in production.

For a local production-preview build, `npm run build --prefix frontend`
defaults to `http://localhost:8000` and `ws://localhost:8000` when deployment
URLs are not configured. Start the initialized API first, then run
`npm run preview --prefix frontend`; the backend's development CORS defaults
allow the Vite preview origin on port `4173`.

Local password-reset links are printed to the backend console when
`EMAIL_MODE=console`. Production requires an SMTP provider; configure `SMTP_HOST`,
`SMTP_FROM`, and the provider credentials before enabling password recovery.

## User and admin workflows

Customers sign in at `/login`, join an open service queue, and receive an
estimated position and wait. Staff sign in at `/staff/login`; queue operations
are restricted to their assigned branch. Administrators sign in at
`/admin/login` and manage organizations, branches, services, counters, queues,
users, and analytics. Administrators can inspect queue requests and customer
ticket details from the queue manager and mark active tickets verified;
verification is recorded without holding up instant joining. Customers may
include an optional service request note of up to 500 characters when joining.
Staff process calls, service, and completion. Public service QR codes open the
branch-specific customer join flow. Frontend route guards are for user
experience; the API enforces authentication and role/branch permissions.

No demo data is loaded at runtime. Register real accounts and have an
authorized administrator create the organization and service resources the
application needs.

Core API operations include:

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

See [docs/queue-engine.md](docs/queue-engine.md) for queue state transitions,
idempotency, and wait-time calculation.

## Authentication, database, and security

Customer, staff, and admin sign-ins use persistent, opaque sessions. The
API hashes session values in SQLite and accepts them as bearer credentials for
cross-origin requests. The frontend keeps the token only in tab-scoped
`sessionStorage`, never `localStorage`; closing the tab clears its copy, and
logout/password reset revoke the server-side session. The API restores a
session with `GET /api/v1/auth/me`.
Registration and login use normalized email/password credentials, and
password-reset tokens are hashed, single-use, and expire after 30 minutes.
Google Sign-In uses Google Identity Services. The Render blueprint and
`backend/.env.example` configure the Web application client ID; the Google
Cloud OAuth client allows the GitHub Pages origin and local development
origins. The backend validates the signed credential and one-time nonce; no
client secret or redirect URI is used. The Google OAuth audience is currently
External/Testing, so only listed test users can sign in until the app is
published.

All accounts, queue resources, queue entries, events, notifications,
preferences, and feedback are stored in SQLite. SQLAlchemy ORM queries and
bound parameters are used to protect database operations from SQL injection.
Foreign keys are enabled; WAL mode and a busy timeout support concurrent
readers while explicit `BEGIN IMMEDIATE` transactions serialize queue writes.

Production uses an absolute SQLite file URL on persistent storage, such as
`sqlite:////var/data/queueless.db`. The backend rejects PostgreSQL and
in-memory production URLs. No Redis service is required; real-time broadcasts,
single-use WebSocket tickets, and rate-limit state are process-local.

## Deployment

The included staged GitHub Actions workflow deploys the frontend to GitHub
Pages after verifying the backend is ready. Set the repository Actions
variables `VITE_API_URL` (HTTPS backend origin), `VITE_WS_URL` (WSS backend
origin), and optionally `VITE_BASE_PATH`. The Render blueprint deploys the
separate FastAPI API with a 50 GB persistent disk at
`/var/data` and runs Alembic migrations before startup. Set Render's
`CORS_ORIGINS` to the exact GitHub Pages origin, `FRONTEND_URL` to the full
Pages app URL (including its repository path when applicable), and
`RESET_PASSWORD_URL` to its `/reset-password` route.

Before deploying, configure the SMTP provider values in the Render dashboard.
The production API intentionally refuses to start without SMTP so password
reset links are delivered privately rather than written to logs. Google Sign-In
uses the configured GIS client ID and GitHub Pages origin. Set
independent production `SECRET_KEY` and `JWT_SECRET` values if not using the
blueprint-generated values. After deployment, provision the first admin with
`python -m app.cli create-admin` in the service shell.

Do not scale the backend to multiple workers or instances: SQLite and WebSocket event fan-out are
single-process. For setup, backup, and scaling limitations, see
[docs/deployment.md](docs/deployment.md),
[docs/database.md](docs/database.md), and
[docs/scaling.md](docs/scaling.md).

## Verification

```sh
cd backend && pytest -q
cd ..
npm run lint --prefix frontend
npm test --prefix frontend
VITE_API_URL=https://api.build.invalid \
VITE_WS_URL=wss://api.build.invalid \
  npm run build --prefix frontend
```

The `.invalid` origins are for local build validation only. Browser tests,
staging checks, and backup/restore verification are described in
[TESTING.md](TESTING.md).
