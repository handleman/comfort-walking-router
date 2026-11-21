# Deployment runbook (035)

A $0 public deployment of the walking app on Render's free web service, so the
real GPS walk (007 AC-8) and the live map look (001 AC-2) can be done on a
phone. One service serves both the FastAPI API and the built Svelte frontend, so
there is no CORS and no API-base-URL to configure.

## One-time setup

1. **Render account** — free, no card required for the free web service.
2. In the Render dashboard: **New + → Blueprint**, point it at this repo, and
   pick the `render.yaml` at the root. It creates a `comfort-walking-router` web
   service from `Dockerfile` (builds the frontend, then serves it from FastAPI).
3. Set the secrets in the service's **Environment** tab (never commit them):
   - `MAPBOX_TOKEN` — required (Mapbox walking geometry + geocoding).
   - `DATABASE_URL` — optional. A **Render free Postgres** connection string (or
     Neon's free tier) enables the saved-routes feature; without it those
     endpoints answer 5xx and the app says so. Render's URL is `postgres://…`
     — paste it as-is (the app normalises it).
   - `OVERPASS_MIRROR_URL` — optional, a mirror for the OSM corridor lookup.
4. Open the service's `.onrender.com` URL on the phone. The first load after
   idle takes ~1 min (cold start); warm it by opening it once before walking.

## Redeploy

- **On push** (if the service is set to auto-deploy) or **Manual deploy → Deploy
  latest commit**. The build runs `npm ci && npm run build` then starts
  `uvicorn app.main:app`.

## Free-tier caveats (Render, 2026)

- **Spin-down:** the service sleeps after 15 min with no traffic; the next
  request cold-starts (~1 min). A personal demo is fine — warm it first.
- **Ephemeral disk:** the SQLite route cache resets on deploy/restart, so the
  first route after a cold start re-fetches providers (a few extra seconds).
- **Bandwidth:** 5 GB/month. A personal walk uses a few MB.
- **Saved-routes:** Render's free Postgres **expires 30 days** after creation
  (then 14 days grace, then deleted — no backups). Fine for a demo, but saved
  routes are lost each cycle. Neon's free tier has no expiry if you want
  persistence. Either way, leave `DATABASE_URL` unset to keep the feature off.

## Local verification

```bash
make test && make e2e && make smoke-live   # app + suite + one live route
docker build -t comfort-walking-router .    # the exact image Render builds
docker run -p 8000:8000 -e MAPBOX_TOKEN=... comfort-walking-router
```
