# Production deployment

The current QueueLess production blueprint runs the Vite frontend on GitHub
Pages and a FastAPI API service on Render. Shared PostgreSQL and Redis are
required for multi-instance deployment. SQLite remains supported for local or
single-instance deployments. The frontend uses HTTPS API calls and WSS for
live queue updates. Never put private values in `VITE_*` variables; Vite embeds
them in public assets.

## Backend requirements

- Keep one API instance while using SQLite. The service uses a single SQLite
  file at
  `/var/data/queueless.db`; the Render blueprint provisions and mounts a
  persistent disk at `/var/data`.
- `DATABASE_BACKUP_DIR=/var/data/backups` stores verified local snapshots on
  that persistent disk. This is not an off-host disaster-recovery copy; export
  snapshots to separately secured storage and test restores.
- Set `ENVIRONMENT=production` and separate random values of at least 32 bytes
  for `SECRET_KEY` and `JWT_SECRET`. The Render blueprint generates these.
- Configure `FRONTEND_URL` as the complete Pages app URL, including the
  repository path for project Pages sites. Set `RESET_PASSWORD_URL` to the
  frontend's `/reset-password` route and `CORS_ORIGINS` to the exact frontend
  origin only (scheme and host, without a path).
- Authenticated frontend requests use revocable bearer session tokens held in
  tab-scoped `sessionStorage`; they do not depend on third-party cookies.
- Production requires `EMAIL_MODE=smtp`; supply `SMTP_HOST`, `SMTP_FROM`, and
  (when required by the provider) `SMTP_USERNAME` and `SMTP_PASSWORD`. The
  service fails closed when SMTP is missing so reset links are not exposed in
  logs.
- `SENTRY_DSN` is optional. SQLite does not require a database server. For
  PostgreSQL, supply a managed PostgreSQL URL privately and configure a
  connection pool suitable for the number of API worker processes.
- Set `REDIS_URL` to a managed Redis instance for every production deployment.
  Redis provides shared WebSocket tickets, rate limits, and pub/sub broadcast
  delivery across API instances.

The included Render blueprint runs `alembic upgrade head` before starting
Uvicorn and uses `/ready` as its health check. PostgreSQL and Redis are
required before scaling beyond one API instance. PostgreSQL provides shared
durable state; Redis provides shared transient state. Capacity still requires
load testing on the selected host.
GitHub Pages is static hosting only: it cannot run the API, store accounts, or
fan out realtime events. The supported GitHub setup is Pages for the frontend
plus the persistent Render API/database. Hosting the frontend on another
platform is supported when it can serve the Vite build and its HTTPS API and
WSS endpoints are configured; configure that exact frontend origin in the
backend CORS list.
All registered accounts and queue activity are stored by the shared API in its
persistent database, so signed-in users see the same live service state from
each device. The Super Admin user list covers registered accounts; anonymous
page visits are not turned into user accounts or tracked as a visitor roster.
Realtime delivery assumes the host supports WebSocket upgrades and keeps all
API traffic on the single configured API instance.

The staged GitHub Actions workflow publishes the frontend on pushes to `main`
or `master`, after the backend readiness check passes. Enable GitHub Pages
with **GitHub Actions** as its source. Configure repository Actions variables:

- `VITE_API_URL`: HTTPS backend origin, for example `https://<api-host>`.
- `VITE_WS_URL`: optional WSS backend origin, for example
  `wss://<api-host>`. If omitted, the workflow derives it from
  `VITE_API_URL` by replacing `https://` with `wss://`.
- `VITE_BASE_PATH`: optional root-relative base path; the workflow detects
  project versus user/organization Pages sites when omitted.
- `VITE_SENTRY_DSN`, `VITE_POSTHOG_KEY`, and `VITE_POSTHOG_HOST`: optional
  frontend monitoring/analytics configuration.

The first deployment requires this order:

1. Deploy the backend and configure PostgreSQL (or single-instance SQLite) and
   Redis until `/ready` returns HTTP 200.
2. Set `VITE_API_URL` as a repository **Variable** under Settings → Secrets
   and variables → Actions. Optionally set `VITE_WS_URL` when WebSockets use a
   different host; otherwise the workflow creates the matching WSS URL
   automatically. Do not put credentials in these values; they are embedded in
   public JavaScript.
3. Enable Settings → Pages → Build and deployment → **GitHub Actions**.
4. Push to `main` or `master`, or run the `QueueLess Stages` workflow manually.

GitHub Pages cannot run Python, SQLite, Redis, background jobs, or WebSockets.
If the backend is stopped, the public shell may still load, but registration,
login, dashboards, queue actions, notifications, and live updates cannot work.
The deployment job therefore refuses to publish unless the configured API
reports ready and the build contains both the project-page route fallback and
static assets.

The Pages artifact includes a `404.html` fallback for direct visits and
refreshes on nested routes. The workflow checks `<VITE_API_URL>/ready` before
publishing; the API must be deployed and its SQLite database initialized.

The Render blueprint configures `FRONTEND_URL`, `RESET_PASSWORD_URL`, and
`CORS_ORIGINS` for the current project Pages URL. If the Pages URL or custom
domain changes, update those values together. CORS uses the origin only,
without the repository path. For each new frontend host, add its HTTPS origin
to `CORS_ORIGINS`, set `FRONTEND_URL` and `RESET_PASSWORD_URL`, set the
GitHub Actions `VITE_API_URL` and `VITE_WS_URL` variables (or equivalent build
environment variables on another static host), and add its origin to the
`VITE_WS_URL` must be a WSS origin for a public HTTPS app.

After the first deployment has applied migrations, use the Render service
shell to run `python -m app.cli create-admin`. Enter initial administrator
credentials at the prompts; do not put them in source control, command-line
arguments, or public frontend variables.

To designate the Super Admin, first ensure the intended local account exists
and its email has been verified through the email verification workflow. Set
`SUPER_ADMIN_EMAIL` in the Render service's private environment to that exact
verified email, then run `python -m app.cli bootstrap-super-admin` in the
service shell. The command will not create accounts, accept an unverified
address, or print a password. It can be rerun safely for the same account.
After it succeeds, sign in at `/super-admin/login`. Do not put this setting in
a frontend `VITE_*` variable.

When the first Super Admin opens the dashboard on an empty installation, a
guided setup form collects the real organization, first branch, service, and
queue details. Submission creates those records atomically and writes an audit
event; it does not insert demonstration data. Additional branches, services,
queues, and counters can then be managed from the Super Admin sections.

## Local setup

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
export DATABASE_URL=sqlite:///./queueless.db
export SECRET_KEY="$(openssl rand -hex 32)"
export JWT_SECRET="$(openssl rand -hex 32)"
python -m app.db.init_db
uvicorn app.main:app --reload --port 8000
```

In another terminal:

```sh
npm ci --prefix frontend
npm run dev --prefix frontend
```

The local API defaults to `http://localhost:8000`; Vite proxies API and
WebSocket traffic to it. `GET /health` checks liveness and `GET /ready`
verifies the SQLite database is reachable.

## Deployment verification

1. Confirm `/health` and `/ready` return HTTP 200.
2. Load the Pages app directly, including a nested route after refresh.
3. Register and sign in using non-demo data.
4. Exercise customer queue joining, staff queue actions, and admin resources.
5. Confirm live queue updates over WSS and refetch after reconnect.
6. Restart the backend and verify accounts, queues, and notifications persist.
7. Verify a database backup can be restored in an isolated service.

Create an online snapshot from the Super Admin dashboard or from the service
shell with `python -m app.cli database-backup`. Restore only during a planned
offline window using `python -m app.cli database-restore <snapshot> --confirm-offline`;
the command creates a pre-restore safety snapshot and requires
`alembic upgrade head` before the service is restarted.

Do not report production readiness until database persistence, backup/restore,
end-to-end user journeys, and performance checks have passed. Test with
disposable data, not customer records.
