# Production deployment

QueueLess production runs the Vite frontend on GitHub Pages and the FastAPI API
as a separate Render service, backed by persistent SQLite storage. The
frontend uses HTTPS for API calls and WSS for live queue updates. Never put
private values in `VITE_*` variables; Vite embeds those values into public
assets.

## Backend requirements

- Use one backend instance and one worker with a persistent local disk. SQLite
  is the only application database; replicas, multiple workers, and shared
  network filesystems are not supported.
- Keep the database on durable disk and configure snapshots/backups. Never use
  an ephemeral filesystem for production data.
- Provide `DATABASE_URL` as an absolute SQLite URL, for example
  `sqlite:////var/data/queueless.db`.
- Set `ENVIRONMENT=production` and separate random values of at least 32 bytes
  for `SECRET_KEY` and `JWT_SECRET`. The backend rejects weak or placeholder
  keys and non-SQLite or in-memory production database URLs.
- Configure `FRONTEND_URL` as the complete Pages app URL, including the
  repository path for project Pages sites. Set `RESET_PASSWORD_URL` to the
  frontend's `/reset-password` route and `CORS_ORIGINS` to the exact frontend
  origin only (scheme and host, without a path).
- Authenticated frontend requests use revocable bearer session tokens held in
  tab-scoped `sessionStorage`; they do not depend on third-party cookies.
  Protect the frontend against XSS, and never log or expose session tokens.
- Production requires `EMAIL_MODE=smtp`; supply `SMTP_HOST`, `SMTP_FROM`, and
  (when required by the provider) `SMTP_USERNAME` and `SMTP_PASSWORD`. Do not
  use console email delivery in production.
- Google Sign-In uses Google Identity Services and the Web application client
  ID configured in `render.yaml`. The Google Cloud OAuth client must allow
  `https://dave870-coder.github.io`, `http://localhost:5173`, and
  `http://127.0.0.1:5173` as **Authorized JavaScript origins**. The backend
  verifies GIS credentials against this client ID; no client secret or
  redirect URI is used. Google OAuth is External/Testing until its audience
  status is explicitly published; while testing, only listed test users can
  sign in.
- `SENTRY_DSN` is optional. Redis is not required or used.

The included `render.yaml` provisions a single Python Render web service with
a 50 GB persistent disk mounted at `/var/data`. Its start command runs
`alembic upgrade head` against the mounted SQLite file before starting Uvicorn.
Set Render's `FRONTEND_URL`, `RESET_PASSWORD_URL`, and `CORS_ORIGINS` as
described above. SQLite's single-writer and local WebSocket model mean this
service must not be scaled to multiple instances.

The staged GitHub Actions workflow publishes the frontend on pushes to `main`
or `master`, after the backend readiness check passes. Enable GitHub Pages
with **GitHub Actions** as its source. Configure repository Actions variables:

- `VITE_API_URL`: backend origin, for example `https://<api-host>`.
- `VITE_WS_URL`: backend WebSocket origin, for example `wss://<api-host>`.
- `VITE_BASE_PATH`: optional root-relative base path; the workflow detects
  project versus user/organization Pages sites when this is omitted.
- `VITE_SENTRY_DSN`, `VITE_POSTHOG_KEY`, and `VITE_POSTHOG_HOST`: optional
  frontend monitoring/analytics configuration. These are not required to
  deploy or use the app.

The Pages artifact includes a `404.html` fallback configured with the same
base path as the app, so direct visits and refreshes on routes such as
`/login` continue to work on project Pages sites. The workflow checks
`<VITE_API_URL>/ready` before publishing; the API must already be deployed and
reachable over HTTPS.

The Render blueprint sets `FRONTEND_URL`,
`RESET_PASSWORD_URL`, and `CORS_ORIGINS` for the project Pages URL
`https://dave870-coder.github.io/QueueLess-Demo-`. If the deployed Pages URL
or custom domain changes, update those three Render values together. CORS uses
the origin only, without the repository path.

Before deployment, configure `SMTP_HOST`, `SMTP_FROM`, and any provider
credentials required by the SMTP service in Render. The production API fails
closed unless SMTP is configured, so password reset tokens are not exposed in
logs. After the first deployment has applied its migrations, use the service's
private shell to run `python -m app.cli create-admin` from the application
directory. Enter the initial administrator credentials at the prompts; do not
put them in source control, command-line arguments, or public frontend
variables.

Previous PostgreSQL deployments are not imported automatically. Export and
verify existing records through a separately planned migration before cutover;
do not point the new SQLite deployment at a PostgreSQL URL.

## Local setup

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=sqlite:///./queueless.db
export SECRET_KEY="$(openssl rand -hex 32)"
export JWT_SECRET="$(openssl rand -hex 32)"
python -m app.db.init_db
uvicorn app.main:app --reload --port 8000
```

In another terminal, start the frontend dev server:

```sh
npm install --prefix frontend
npm run dev --prefix frontend
```

The local API defaults to `http://localhost:8000`; the frontend dev server
proxies requests to that origin. `GET /health` is a liveness check and
`GET /ready` verifies that the SQLite database is reachable.

For a local production preview, run `npm run build --prefix frontend` without
setting `VITE_API_URL` or `VITE_WS_URL`; non-CI local builds point at
`http://localhost:8000` and `ws://localhost:8000`. Start the migrated backend,
then run `npm run preview --prefix frontend`. The development CORS defaults
include the preview origin `http://localhost:4173`.

## Deployment verification

After deployment, verify against the real service:

1. `/health` and `/ready` return HTTP 200.
2. The Pages app loads directly, including a nested route after refresh.
3. Customer registration, login, and queue joining work using non-demo data.
4. Staff can call, start, and complete a queue entry; admin resource controls
   are restricted to admins and persist changes.
5. Connected clients receive queue updates over WSS and can recover by
   refetching current state after reconnect.
6. Restarting the backend preserves accounts, queues, and notifications.
7. Measure the live app on representative mobile broadband with browser cache
   disabled and a warm backend. Target largest-contentful paint and initial
   service-list readiness under 3 seconds at the 75th percentile. Repeat with
   a cold service separately; host startup and network conditions can exceed
   the target and cannot be bounded by frontend code alone.

Do not report production readiness until the persistent-disk restart check and
the end-to-end user journeys and performance checks have passed. Test with
disposable data; do not run mutating acceptance tests against real customer
records.
