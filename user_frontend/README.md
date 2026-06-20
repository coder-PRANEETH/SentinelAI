# SentinelAI — Public Incident Reporting (user_frontend)

A separate, public-facing Next.js site that lets regular road users report
incidents (car breakdown, accident, road block, medical emergency) in a
few taps. This is **independent** of the operator/admin dashboard in
`../frontend` — different app, different port, no shared auth.

## Pages

| Route | Purpose |
|---|---|
| `/` | Landing page — "Report Road Incidents Instantly" + incident type cards |
| `/report` | Incident type selection |
| `/report/car-breakdown` | Report form (vehicle type, issue, description, phone, geolocation + map) |
| `/report/safe-location` | Nearest safe location / police station suggestion + map |
| `/report/success` | Confirmation with mock incident reference ID |

## Run it

```bash
cd user_frontend
npm install
npm run dev
```

Opens on **http://localhost:3001** (the operator frontend uses 3000, so
both can run side by side).

Optionally copy `.env.local.example` to `.env.local` to point at different
backend URLs:

```bash
cp .env.local.example .env.local
```

```
NEXT_PUBLIC_FINAL_ENDPOINTS_API_URL=http://127.0.0.1:5000
NEXT_PUBLIC_BACKEND_API_URL=http://127.0.0.1:5001
```

## Backend integration notes

- `final_endpoints` (port 5000) exposes a public, unauthenticated
  `GET /stations` with live resource counts (officers/vehicles/etc.) but
  **no coordinates**.
- `backend` (port 5001) has the authoritative station coordinates, but its
  `/stations` route requires an operator JWT — not available to anonymous
  public users.
- There is currently **no public "create incident" endpoint**. The "Safe
  Location" step therefore uses a small bundled list of real Bengaluru
  police stations/safe stops (`src/lib/stationsData.ts`) for distance
  ranking, and incident submission (`src/lib/api.ts` →
  `submitIncidentReport`) tries `POST {BACKEND_BASE}/incidents` first, then
  falls back to a locally generated mock reference ID so the flow keeps
  working end-to-end.
- Search for `TODO(backend)` in `src/lib/api.ts` and `src/lib/stationsData.ts`
  for the exact spots to wire up once public endpoints exist.

## Tech

- Next.js 16 (App Router) + TypeScript, matching the existing `frontend/`
- MapLibre GL JS with the same dark OpenFreeMap tile style as the operator
  map (`frontend/src/components/map/BengaluruMap.tsx`), reimplemented as
  `src/components/map/PublicMap.tsx` for the simpler public use case
- Tailwind v4 + the same SentinelAI brand colors (lime accent `#CDFF50`,
  dark `#111`-family surfaces), adapted to a fully dark theme for the
  public "emergency-tech" look
- No new dependencies beyond what `frontend/` already uses (`maplibre-gl`,
  `next`, `react`) — no auth, no state library; in-progress reports are
  passed between steps via `sessionStorage` (`src/lib/reportStore.ts`)

## What was *not* touched

Nothing in `frontend/`, `backend/`, or `final_endpoints/` was modified.
This is a fully standalone app inside `user_frontend/`.
