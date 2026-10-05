# Deployment

Build the frontend with `npm --prefix frontend run build` and deploy
`frontend/dist` to GitHub Pages or Cloudflare. Run the backend with
`uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`, providing the
backend environment variables from `backend/.env.example`.
