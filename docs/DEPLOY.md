# Deployment

The app is two pieces: a FastAPI backend (must be Python — Genblaze is a Python SDK) and a
static React frontend. Deploy the backend first, then point the frontend at it.

## Backend → Render (or Railway / Fly)

1. Push this repo to GitHub.
2. On [Render](https://render.com): **New → Web Service**, pick the repo.
   - Root directory: `backend`
   - Runtime: Python 3.12
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Add environment variables (from `backend/.env.example`): `B2_KEY_ID`, `B2_APP_KEY`,
   `B2_BUCKET`, `B2_REGION`, `GMI_API_KEY`, and set `CORS_ORIGINS` to your frontend URL
   (e.g. `https://veritas-studio.vercel.app`).
4. Note: the SQLite index is ephemeral on most PaaS free tiers (resets on redeploy). That's
   fine — Backblaze B2 holds the durable assets + manifests. For persistence, attach a disk
   and set `DB_PATH` to a path on it.

`render.yaml` is included for one-click blueprint deploys (still set the secrets in the
dashboard).

## Frontends → Vercel (or Netlify) — two static projects

This is a **pnpm + Turborepo** monorepo, so create **two** Vercel projects from the same repo
(one for the customer app, one for the admin console). Vercel auto-detects pnpm from
`pnpm-lock.yaml`.

For each project:
1. On [Vercel](https://vercel.com): **New Project**, import the repo.
   - Root directory: `customer` (first project) / `admin` (second project)
   - Framework preset: Vite  ·  Output dir: `dist`
   - Build command: `pnpm build` (Turbo will build that app), or leave Vercel's default.
2. Env vars: set `VITE_API_BASE` = your backend URL (e.g. `https://veritas-api.onrender.com`)
   on both. On the **admin** project also set `VITE_CUSTOMER_URL` = the customer app's URL.
3. `customer/vercel.json` and `admin/vercel.json` rewrite all routes to `index.html` so deep
   links (Content Passport pages) work.

> On the backend, set `ENV=production`, `CORS_ORIGINS` to both deployed app URLs, a random
> `ADMIN_TOKEN`, and `ADMIN_PASSWORD_HASH` — a salted scrypt hash generated locally with
> `python -m app.hashpw` (the plaintext password is never stored server-side). The app refuses
> to boot in production if any of these are missing.

## Local-only alternative (simplest for judging)

You can also submit with the app running locally and a tunnel:

```bash
# terminal 1 — everything (backend + both apps)
pnpm dev
# terminal 2 (expose the customer app for judges, optional)
npx localtunnel --port 5173      # or ngrok http 5173
```

A deployed URL is stronger for the "production readiness" criterion, but a stable tunnel works.
