#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend_dir="$root_dir/backend"
frontend_dir="$root_dir/frontend"

if [[ ! -x "$backend_dir/.venv/bin/uvicorn" ]]; then
  echo "Missing backend/.venv. Create it and install backend/requirements.txt first." >&2
  exit 1
fi

if [[ ! -x "$frontend_dir/node_modules/.bin/vite" ]]; then
  echo "Missing frontend dependencies. Run npm ci --prefix frontend first." >&2
  exit 1
fi

cleanup() {
  trap - TERM INT EXIT
  [[ -n "${backend_pid:-}" ]] && kill "$backend_pid" 2>/dev/null || true
  [[ -n "${frontend_pid:-}" ]] && kill "$frontend_pid" 2>/dev/null || true
}
trap cleanup TERM INT EXIT

(
  cd "$backend_dir"
  exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "${BACKEND_PORT:-8000}"
) &
backend_pid=$!

for _ in {1..30}; do
  if curl --fail --silent "http://127.0.0.1:${BACKEND_PORT:-8000}/health" >/dev/null; then
    break
  fi
  sleep 1
done

if ! curl --fail --silent "http://127.0.0.1:${BACKEND_PORT:-8000}/health" >/dev/null; then
  echo "QueueLess API did not become healthy." >&2
  exit 1
fi

(
  cd "$frontend_dir"
  VITE_API_URL="http://127.0.0.1:${BACKEND_PORT:-8000}" \
  VITE_WS_URL="ws://127.0.0.1:${BACKEND_PORT:-8000}" \
    exec npm run dev -- --host 127.0.0.1 --port "${FRONTEND_PORT:-5173}"
) &
frontend_pid=$!

echo "QueueLess API: http://127.0.0.1:${BACKEND_PORT:-8000}"
echo "QueueLess web app: http://127.0.0.1:${FRONTEND_PORT:-5173}"
wait "$frontend_pid"
