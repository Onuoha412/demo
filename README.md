# QueueLess

QueueLess is a production-quality foundation for a digital queue-management
platform. This stage intentionally focuses on the application shell and health
foundations; advanced queue operations, AI, Redis, WebSockets, and notifications
are deferred.

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

## Verification

```bash
npm run build --prefix frontend
cd backend && pytest -q
```

The backend exposes `GET /health` and `GET /api/v1/health`.
