# 035 Free Deployment — Spec

Product spec (the comfort route guide): a $0 public deployment so the operator
can run the two human gates — a real GPS walk (007 AC-8) and a live map look
(001 AC-2) — on a phone, not a laptop with `make dev`.

## Problem

The app only runs locally (`make dev` → backend :8000 + frontend :5173). The two
acceptance criteria that no automated test can close are both *device* actions:
looking at the live map (real OSM corridor + weather behind the route) and
walking a real route while the app tracks the device GPS. Browser geolocation
only works over HTTPS, so "deploy it somewhere reachable from my phone" is the
only way to do them. The operator wants that to cost **$0**.

## Goal

A free, HTTPS, public deployment of the walking app — the Svelte frontend and
the FastAPI backend on one origin — reachable from a phone browser, using the
live providers (Mapbox, Overpass, weather), with no per-month fee.

## Investigation (2026)

| Platform | Free? | Notes |
| --- | --- | --- |
| **Render** (web service) | ✅ | 512 MB / 0.1 CPU, spins down after 15 min idle (~1 min cold start), ephemeral filesystem, 5 GB/mo bandwidth, HTTPS by default. |
| Heroku | ❌ | Eco $5/mo since Nov 2022. |
| Fly.io | ❌ | No free tier for new users (card required). |
| Railway | ❌ | $5 one-time / $1 free credit — a few hours of runtime. |
| Vercel | ⚠️ | Free static is fine, but serverless Python has cold starts, no persistent disk, and function time caps that the ~40 s Overpass corridor call would exceed. Frontend-only fallback. |
| Koyeb | ❌ | Card + $29 hold required. |
| **Neon** (Postgres) | ✅ | 1 GB, 100 CU-hrs/mo, scales to zero, no expiration — the free DB for saved-routes. |

**Recommendation:** Render's free web service, one service serving both the
FastAPI API and the built `frontend/dist/`. The frontend already calls the API
on relative paths (`/route`, `/geocode`, `/saved-routes`), so a same-origin
deploy needs **no CORS and no API-base-URL rework**. Saved-routes (Postgres) is
optional for the walk demo: use Neon's free tier, or leave it down (the app
already skips/says-so without `DATABASE_URL`).

## Scope

- A deploy config for Render (`render.yaml` blueprint or a Dockerfile + start
  command) that builds the frontend (`npm ci && npm run build`) and serves it
  from the FastAPI app.
- `app/main.py` mounts the built `dist/` as static files and serves `index.html`
  at `/` (only when the build exists — local `make dev` is unchanged).
- Documented env vars: `MAPBOX_TOKEN` (backend-only), `DATABASE_URL`
  (optional, Neon), `OVERPASS_MIRROR_URL` (optional).
- A `docs/runbooks/deploy.md` page: the exact Render/Neon setup, the free-tier
  caveats (spin-down, cold start, ephemeral disk, bandwidth), and how to update
  the deployment.
- Reconciling any frontend API path that does not match a backend route
  (the geocode suggestion fetch uses `/api/geocode/suggest`).

## Non-goals

- A paid plan, autoscaling, custom domain, or uptime SLA.
- CI/CD beyond "redeploy on push / manual deploy".
- Persistent route cache (the SQLite cache may reset; that is fine).

## Acceptance criteria

- **AC-1 — Reachable over HTTPS at $0.** `curl https://<app>.onrender.com/` returns
  the app's HTML, and `POST /route` on the same origin returns a route, without
  any CORS error.
- **AC-2 — Live map look works.** From a phone browser, a search → route shows
  the map, the real corridor/weather (a stated data gap when Overpass is busy is
  acceptable), and the comfort bands.
- **AC-3 — Real GPS walk works.** Over HTTPS, the walk mode reads the device
  geolocation, starts a route, and shows the off-route/reroute banner when the
  operator walks away from it.
- **AC-4 — No secret is committed.** `MAPBOX_TOKEN` and `DATABASE_URL` live only
  in the platform's env vars; the repo carries placeholders, never the values.
- **AC-5 — The cost is $0.** The deployment uses only the free tier; no card on
  file is required for Render's free web service.
- **AC-6 — Documented.** `docs/runbooks/deploy.md` names the exact steps and the
  free-tier caveats; `README.md` links it.

## Success definition

The operator opens the deployed URL on a phone, looks at the live map, and
completes a real GPS walk with the app tracking and rerouting — for $0/month.
