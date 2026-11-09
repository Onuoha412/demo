# Testing

Backend integration tests create a disposable SQLite database in the system
temporary directory, apply the application migrations, and remove the database
after the test session. The tests do not require a database server or external
credentials.

## Backend

```sh
cd backend
pip install -r requirements.txt
pytest -q
```

The suite exercises registration and sessions, case-insensitive email
uniqueness, password reset, authorization, queue transitions, notifications,
WebSockets, schema constraints, and concurrent queue joins using SQLite.
`TEST_DATABASE_URL` can point to a dedicated disposable SQLite file for
debugging; tests reject non-SQLite backends and may reset/downgrade the
configured database.

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

The full customer/staff/admin realtime journey is skipped unless
`E2E_ADMIN_EMAIL`, `E2E_ADMIN_PASSWORD`, and `E2E_DATA_DISPOSABLE=1` are set.
Point `E2E_API_URL` at an isolated API with a disposable administrator; the
test creates accounts, queues, and tickets. The Playwright projects run serially
because they share and mutate that API. For a dedicated test API, raise
`AUTH_RATE_LIMIT_LOGIN` and `AUTH_RATE_LIMIT_REGISTER` enough for the
three-browser run; do not relax these limits on production.

Do not use production credentials or point mutating tests at a database with
data to preserve.

## Load profiles

`loadtests/queue.js` provides four configurable k6 profiles. Each profile
registers fresh accounts and then runs authenticated queue joins and paginated
queue reads:

| Profile | Registered accounts | Active VUs |
|---|---:|---:|
| A | 100 | 20 |
| B | 400 | 100 |
| C | 780 | 200 |
| D | 780 | 780 |
| E | 750 | 750 |

Run only against an isolated, disposable deployment with a published service,
an open queue, and registration rate limits configured for the setup phase:

```sh
PROFILE=A \
ISOLATED_TEST_TARGET=YES \
BASE_URL=http://127.0.0.1:8000 \
QUEUE_ID=<queue-id> \
LOAD_TEST_PASSWORD=<test-only-password> \
k6 run loadtests/queue.js
```

Set `PROFILE=B`, `C`, or `D` to select another profile. `VUS`,
`REGISTERED_USERS`, and `DURATION` can override the profile values. The test
leaves its generated customer accounts and queue activity in the target
database; discard that database after the run. k6 reports request duration
percentiles, request rates, failures, checks, and the custom
`queue_join_latency`, `queue_read_latency`, and `database_lock_errors`
metrics. This script does not measure WebSocket delivery latency, database
transaction duration, CPU, or memory, and profiles have not been certified as
capacity guarantees. Record results from the actual target host before making
any capacity claim.

The backend also includes an exact 750-user SQLite persistence regression:

```sh
cd backend
.venv/bin/python -m pytest -q tests/test_sqlite_user_capacity.py
```

Profile `E` is the end-to-end 750-user workload: it registers 750 customers,
then exercises authenticated queue joins and paginated queue reads. Run it only
against an isolated database with a published service and open queue.
