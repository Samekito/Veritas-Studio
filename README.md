# Veritas Studio — Verifiable AI Media

> Generate campaign-ready media from a one-line brief through a multi-model **Genblaze**
> pipeline, and ship every asset with a cryptographic **Content Passport** — provenance,
> lineage, and a public verifier — all stored and orchestrated on **Backblaze B2**.

Built for the [Backblaze Generative Media Hackathon](https://backblaze-generative-media.devpost.com/).

---

## Why this exists

Anyone can call a text-to-video API. The hard, *valuable* problems are everything around it:

- **Trust** — As AI media floods the web (and regulations like the EU AI Act demand
  disclosure), brands and creators need to *prove* how an asset was made.
- **Orchestration** — Real output is a chain across providers (script → image → video →
  voiceover) with fallbacks when a model is down.
- **Asset management** — Generated media and its metadata have to live somewhere durable,
  deduplicated, and searchable.

Veritas Studio makes provenance a **first-class, user-facing feature**, powered by exactly
the stack the hackathon is built on: Genblaze for orchestration + provenance, Backblaze B2
for storage and data orchestration, GMI Cloud for the models.

## What it does

1. **Brief → Plan.** A short brief is expanded into image, motion, and voiceover prompts.
2. **Multi-step Genblaze pipeline.** `text → keyframe image (Seedream) → image-to-video
   (Kling, conditioned on the keyframe) → voiceover (MiniMax TTS via GMI)`, with
   **automatic model fallback** per step for reliability.
3. **Everything to B2.** Each asset *and* a tamper-evident provenance manifest are written to
   Backblaze B2 using a content-addressable layout (identical bytes stored once).
4. **Content Passport.** Every run gets a public page showing the verified SHA-256 manifest,
   per-step model lineage, cost, and a **"download verifiable copy"** with the manifest
   embedded *inside* the media file.
5. **Verify anything.** Drop any file into the Verify page — we extract and cryptographically
   verify its Genblaze manifest. No account, no trust required.
6. **Operate it.** An **Admin · Operations** dashboard gives a live view of every run:
   provider/credential health, per-step status (which model succeeded/failed and why —
   e.g. surfacing an out-of-credits `402`), verification state, cost, plus retry/delete.

## Architecture

```
 React/Vite SPA  ──HTTP──►  FastAPI  ──►  Genblaze Pipeline ──► GMI Cloud models
 (brief, library,            (jobs,         (orchestration +      (Seedream / Kling /
  passport, verify)           verify)        provenance)           MiniMax TTS)
                                │                   │
                                │                   ▼
                                │           ObjectStorageSink
                                ▼                   │
                          SQLite index  ◄───────────┘  assets + manifests
                          (fast queries)            Backblaze B2 (source of truth)
```

- **Genblaze** (`backend/app/pipelines.py`) — builds and runs the multi-step `Pipeline`,
  wires `input_from` chaining and `fallback_models`, and captures the provenance `Manifest`.
- **B2** (`backend/app/storage.py`) — `S3StorageBackend.for_backblaze(...)` +
  `ObjectStorageSink` with `KeyStrategy.CONTENT_ADDRESSABLE`.
- **Provenance verifier** (`backend/app/media_tools.py`) — embeds/extracts manifests in
  media files and verifies them.

## AI providers & models

| Stage | Provider (via Genblaze) | Default model | Fallback |
|-------|-------------------------|---------------|----------|
| Keyframe image | GMI Cloud (`GMICloudImageProvider`) | `seedream-5.0-lite` | `gemini-2.5-flash-image` |
| Image→Video | GMI Cloud (`GMICloudVideoProvider`) | `Kling-Image2Video-V2.1-Master` | configurable |
| Voiceover | GMI Cloud (`GMICloudAudioProvider`) | `minimax-tts-speech-2.6-turbo` | — |

All models are swappable via environment variables — no code changes (Genblaze abstracts the
providers). See `backend/.env.example`.

## Quick start

**Prerequisites:** Python 3.11 or 3.12 (see note below), Node 18+, a Backblaze B2 bucket, and
a GMI Cloud API key.

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate      |  macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill in B2_* and GMI_API_KEY

# Prove the stack works (generates 1 image to your B2 bucket):
python smoke_test.py

# Run the API:
uvicorn app.main:app --reload --port 8000
```

### 2. Apps (pnpm workspaces + Turborepo)

This is a **pnpm** monorepo orchestrated with **Turborepo**. Dependencies are hoisted to the
root; install once at the root and drive everything from there.

```bash
# from the repo root (pnpm 9+; `corepack enable` if you don't have it)
pnpm install

# run EVERYTHING (backend + customer + admin) with one command:
pnpm dev

# …or individually:
pnpm dev:backend     # FastAPI on http://localhost:8000  (uses backend/.venv)
pnpm dev:customer    # customer app on http://localhost:5173
pnpm dev:admin       # admin console on http://localhost:5174
pnpm dev:web         # both web apps via `turbo run dev`

# build (Turbo-cached):
pnpm build           # turbo run build  → customer + admin
```

- **Customer app** (`customer/`, :5173) — Create / Library / Passport / Verify.
- **Admin console** (`admin/`, :5174) — super-admin **login-gated** operations dashboard
  (dev: set `ADMIN_PASSWORD` in `backend/.env`; prod verifies against `ADMIN_PASSWORD_HASH`).
- **Shared package** (`@veritas/shared`) — types, API client, and design system used by both.

Both apps proxy `/api` to the backend on :8000 in dev. `pnpm dev:backend` expects the Python
venv at `backend/.venv` (see step 1).

> **Python version note:** Genblaze targets Python 3.11+. The provider wheels are best tested
> on **3.11/3.12**. If `pip install` fails on a very new interpreter (e.g. 3.14), create the
> venv with `py -3.12 -m venv .venv`.

## Deployment

- **Customer & Admin** → Vercel/Netlify (two static projects). For each, set the root to
  `customer/` or `admin/`, build with `npm run build` (Vite), and set `VITE_API_BASE` to your
  backend URL (admin also takes `VITE_CUSTOMER_URL`). SPA fallback configs included
  (`customer/vercel.json`, `admin/vercel.json`).
- **Backend** → Render/Railway/Fly. Start command:
  `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Set all `backend/.env` vars as
  environment variables (incl. `ENV=production`, `ADMIN_TOKEN`, `ADMIN_PASSWORD_HASH` from
  `python -m app.hashpw`, and `CORS_ORIGINS` with both app URLs). `render.yaml` included.

See [docs/DEPLOY.md](docs/DEPLOY.md).

## Repo layout

```
backend/    FastAPI + Genblaze pipeline + B2 + SQLite index + smoke_test.py
customer/   Vite + React app — Create / Library / Passport / Verify   (:5173)
admin/      Vite + React app — login-gated Operations dashboard        (:5174)
shared/     @veritas/shared — types, API client, shared design system
package.json / pnpm-workspace.yaml / turbo.json  — pnpm workspace + Turborepo root
docs/       Submission writeup, demo script, deploy guide
```

## License

MIT.
