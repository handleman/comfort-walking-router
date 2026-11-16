# 035 Free Deployment — Plan

## Recommendation

Render free web service, one origin: the FastAPI app serves the API and the
built Svelte `dist/`. Neon free Postgres for saved-routes (optional). Rationale:

- The frontend already calls the API on **relative paths** (verified:
  `App.svelte`, `walkMode.ts` fetch `/route`; `savedRoutes.ts` fetches
  `/saved-routes*`; `SearchInput.svelte` defaults `baseUrl=''`). Same-origin
  needs no CORS and no base-URL plumbing.
- `app/main.py` has **no `StaticFiles` mount and no `CORSMiddleware`** today, so
  the only backend change is "serve the built frontend when it exists".
- Render is the only mainstream host with a real, card-free free web service in
  2026 (Fly/Railway/Heroku/Koyeb are gone or card-gated; Vercel's serverless
  Python can't survive the ~40 s Overpass call and has no disk).

## Shape

```
phone browser ──HTTPS──► Render web service (FastAPI)
                           ├── GET  /                → frontend/dist/index.html
                           ├── POST /route           → live Mapbox + Overpass + weather
                           ├── GET  /geocode, /reverse
                           └── /saved-routes*        → Neon Postgres (optional)
```

## Steps

1. **Static serving in `app/main.py`.** Mount `frontend/dist` at `/` with an
   `index.html` fallback, but only when `dist/index.html` exists (so `make dev`
   and the tests are unchanged). Keep the API routes (`/route`, `/geocode`,
   `/saved-routes`) registered before the SPA fallback.
2. **Reconcile the geocode path.** `SearchInput`/`suggestions.ts` fetch
   `${baseUrl}/api/geocode/suggest`, but the backend mounts `/geocode`. Confirm
   the real endpoint and align one side (rename the frontend path or add an
   `/api/geocode/suggest` alias) — without this the search box 404s in prod.
3. **Deploy config.** Add a `render.yaml` (or `Dockerfile` + `Procfile`) with:
   build command `npm --prefix frontend ci && npm --prefix frontend run build`,
   start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, and the env
   keys (`MAPBOX_TOKEN`, `DATABASE_URL`, `OVERPASS_MIRROR_URL`) as
   `envVarGroups`/`envVars` referencing platform secrets. Add `.dockerignore`
   already covers node_modules/venvs.
4. **Env vars.** `MAPBOX_TOKEN` (backend-only; the frontend uses Leaflet, no
   key), optional `DATABASE_URL` from Neon. Document in `docs/runbooks/deploy.md`.
5. **DB (optional).** Neon free Postgres → `DATABASE_URL`; without it, the app
   must keep skipping saved-routes gracefully (it already does).
6. **Runbook.** `docs/runbooks/deploy.md`: create the Render service, set the
   secrets, deploy, the free-tier caveats (spin-down after 15 min idle → ~1 min
   first-load, ephemeral disk → route cache resets, 5 GB/mo bandwidth), and how
   to redeploy. Link from `README.md`.

## Risks

- **Cold start ~1 min** after idle: acceptable for a personal demo; the walk
  operator warms it by opening the URL first.
- **Overpass 502/busy**: already a stated data gap in the app; the mirror env
  var mitigates.
- **Bandwidth / spin-down policy change** (Render cut free bandwidth Apr 2026):
  the spec records the tier's current terms; if it degrades, the fallback is
  Vercel (frontend) + a second free backend, or a self-hosted box.
- **Secrets leak**: `MAPBOX_TOKEN` is a real key; it must never be committed —
  platform env vars only (AC-4).
