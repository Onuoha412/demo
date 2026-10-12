# Testing

Backend tests use an isolated temporary SQLite database by default. PostgreSQL
and Redis services or staging credentials are not needed to run the local or
CI suites.

## Backend

```sh
cd backend
pip install -r requirements.txt
pytest -q
```

The suite runs migrations and exercises registration, cookie-backed session
restoration and revocation, case-insensitive email uniqueness, password reset
token expiry/reuse behavior,
authorization, queue transitions, notifications, WebSockets, schema
constraints, and concurrent queue joins against SQLite. `TEST_DATABASE_URL`
may point to a separate SQLite file, but non-SQLite test URLs are rejected.
Tests never connect to production data.

## Frontend

```sh
npm ci --prefix frontend
npm run lint --prefix frontend
npm test --prefix frontend
VITE_API_URL=https://api.build.invalid \
VITE_WS_URL=wss://api.build.invalid \
  npm run build --prefix frontend
```

The `.invalid` origins are only for a production-build check and do not make
network requests. Real deployments must configure the actual HTTPS API and WSS
origins.

## End-to-end and staging checks

Frontend browser tests can be run with the existing Playwright setup:

```sh
cd frontend
npx playwright install chromium firefox webkit
npm run test:e2e
```

Any mutating full-system test should use an isolated deployment and disposable
accounts/queues. Do not use production credentials or point tests at a
production database. Hosting readiness also requires verifying that a service
restart preserves SQLite data on its persistent disk.
