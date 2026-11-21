# 035 Free Deployment — Tasks

- [x] T1 (AC-1): Serve the built frontend from `app/main.py` — mount `frontend/dist` at `/` with an `index.html` fallback, guarded so it only activates when `dist/index.html` exists (local `make dev` and the app tests stay unchanged). Test: a startup test that a built dist is served and that the API routes still win.
- [x] T2 (AC-1): Reconcile the geocode suggestion path — the frontend fetches `/api/geocode/suggest` but the backend mounts `/geocode`; align them (one side) and keep `npm run check` green.
- [x] T3 (AC-1, AC-4): Add the Render deploy config (`render.yaml` or `Dockerfile` + start command): build `npm --prefix frontend ci && npm --prefix frontend run build`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, env keys `MAPBOX_TOKEN`/`DATABASE_URL`/`OVERPASS_MIRROR_URL` from platform secrets (no committed values).
- [x] T4 (AC-2, AC-3, AC-5): Deploy to Render free, set the secrets, and verify over HTTPS: the page loads, `POST /route` returns a route, and the phone's geolocation is accepted by the browser.
- [x] T5 (AC-6): Write `docs/runbooks/deploy.md` (exact Render/Neon setup, the free-tier caveats, how to redeploy) and link it from `README.md`'s Verification section.
