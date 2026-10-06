# Deployment

Build the frontend with `npm --prefix frontend run build` and deploy
`frontend/dist` to GitHub Pages or Cloudflare. Run the backend with
`uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`, providing the
backend environment variables from `backend/.env.example`.
Generate a unique `JWT_SECRET_KEY` of at least 32 bytes (for example with
`openssl rand -hex 32`). The API refuses to start with a missing, weak, or
known placeholder key. Do not use the test-only key or commit production
secrets. Authenticated WebSockets use short-lived one-time tickets obtained
over an authenticated POST; bearer access tokens are never placed in URLs.
