# SentinelAI: Free-Tier Deployment Runbook

This runbook outlines the steps to deploy the full SentinelAI stack using strictly free-tier services. We have actively replaced components that previously required paid add-ons (such as persistent disks) with robust, free-tier compatible alternatives.

## Service Map & Free Tier Validation

| Service | Hosting | Description & Free Tier Details |
|---|---|---|
| **Admin Dashboard** (`frontend/`) | Cloudflare Pages | Free static hosting. Unlimited bandwidth, 500 builds/month limit. |
| **Citizen App** (`user_frontend/`) | Cloudflare Pages | Free static hosting. Uses the same limits as above. |
| **Backend API** (`backend/`) | Render Free Web Service | Free REST API. Spin-downs occur after 15m of inactivity. 512 MB RAM. |
| **AI Models & Sim** (`final_endpoints/`) | Render Free Web Service | Free REST API handling FAISS/CatBoost. Spin-downs occur. 512 MB RAM. |
| **Database** (`resources.db` & Core DB) | Supabase (Postgres) | Free hosted Postgres. Replaced local SQLite (`resources.db`) to avoid paid Render disks. |

## Caveats & Constraints

1. **Cold Starts:** Since Render's free tier spins down inactive web services after 15 minutes, the **first request** to the API (or initial dashboard load) will experience a delay of 30-60 seconds as the container boots.
2. **Pre-Demo Warm Up:** **ALWAYS** ping both backends (`/health` or `/docs`) 5-10 minutes prior to any demo to prevent the cold start from impacting the live presentation.
3. **Memory Limits (512MB RAM):** 
   - `final_endpoints/` uses large models (FAISS, SentenceTransformers). We utilize **lazy-loading** logic so they are not loaded into RAM until the specific historical search endpoint is triggered.
   - `backend/` uses `faster-whisper`. We lazy-load the `WhisperModel` inside the `transcribe_audio_file` method instead of at the module level.
4. **Bandwidth:** Render provides 100GB/month bandwidth on free web services, which is well within our requirements.
5. **Database Pause:** Supabase will pause projects after 1 week of zero activity. You must log into the Supabase dashboard to unpause it if it has been idle.

## Architecture Refactor: SQLite to Supabase Migration

Previously, the `final_endpoints/models.py` relied on a local `resources.db` SQLite file. Render does not offer persistent disks on its free tier, so any container restarts or deploys would erase live resource tracking allocations.

**Resolution:** We migrated the Resource Tracker's database connection from `sqlite3` to `psycopg2`. The exact same schema logic is used, but it now connects directly to the **existing free Supabase Postgres DB**. This completely eliminates the need for a persistent disk while preserving all state logic and function signatures.

---

## Deployment Steps

### 1. Database (Supabase) Setup
We are using the single Supabase instance already provisioned. Ensure the following connection string is secured:
- `DATABASE_URL`: `postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres`

### 2. Backends (`backend/` and `final_endpoints/`) on Render
Create two **New Web Services** on Render connected to this repository.

**Service 1: Sentinel Backend**
- **Root Directory:** `backend`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Environment Variables:**
  - `DATABASE_URL`: `<Supabase Connection String>`
  - `SUPABASE_URL`: `<Supabase Project URL>`
  - `SUPABASE_ANON_KEY`: `<Supabase Anon Key>`

**Service 2: Sentinel AI & Models**
- **Root Directory:** `final_endpoints`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn models:app`
- **Environment Variables:**
  - `DATABASE_URL`: `<Supabase Connection String>`
  - `BACKEND_API_URL`: `https://[RENDER_BACKEND_URL].onrender.com`

*Note: The `render.yaml` file in the repository root has been updated to support Blueprint deployment on Render if preferred.*

### 3. Frontends on Cloudflare Pages
Create two new **Cloudflare Pages** applications connected to the repository.

**App 1: Sentinel Admin (`frontend/`)**
- **Framework:** Next.js
- **Build Command:** `npx @cloudflare/next-on-pages`
- **Build Output Directory:** `.vercel/output/static`
- **Compatibility Flags:** You MUST add `nodejs_compat` in the project settings -> Settings -> Functions -> Compatibility Flags.
- **Environment Variables:**
  - `NEXT_PUBLIC_SUPABASE_URL`: `<Supabase Project URL>`
  - `NEXT_PUBLIC_SUPABASE_ANON_KEY`: `<Supabase Anon Key>`
  - `NEXT_PUBLIC_API_URL`: `https://[RENDER_BACKEND_URL].onrender.com`
  - `NEXT_PUBLIC_FINAL_ENDPOINTS_API_URL`: `https://[RENDER_FINAL_ENDPOINTS_URL].onrender.com`

**App 2: Sentinel User Reporting (`user_frontend/`)**
- Use the same settings as above, but set the root directory to `user_frontend/`.

### 4. Cross-Origin Resource Sharing (CORS) Security
Both backends have been updated to explicitly allow the Cloudflare Pages `*.pages.dev` origins. This ensures only your designated frontends can communicate directly with the AI dispatch and management APIs.

---

## Pre-Flight Smoke Test Checklist

Once all 4 services report as "Deployed", perform the following verifications:
- [ ] Send a GET request to the backend health endpoint (e.g., `https://[RENDER_BACKEND_URL].onrender.com/docs`).
- [ ] Open the Admin Dashboard URL in your browser. Verify the real-time queue loads without errors.
- [ ] Click through to a Station Resource Allocation panel. Verify that resource changes persist across page reloads (confirming Supabase Postgres writes).
- [ ] Submit an incident via the User Reporting app. Verify it triggers the webhook, completes the AI evaluation, and appears on the active dashboard.
