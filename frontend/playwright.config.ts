import { defineConfig, devices } from '@playwright/test'

const baseURL = process.env.BASE_URL || 'http://localhost:5173'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : [['list']],
  use: {
    baseURL,
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      // `python -m uvicorn` with the repo venv: the suite must not depend on
      // the caller's PATH having `.venv/bin` (it does not when npm is run
      // directly; a fresh shell then fails with `uvicorn: command not found`).
      command: './.venv/bin/python -m uvicorn app.main:app --port 8000',
      // `/` has no route (404), so the readiness probe must hit the docs page.
      url: 'http://localhost:8000/docs',
      // The config lives in frontend/, the FastAPI app in the repo root; and
      // without ROUTE_FIXTURES the suite makes live Nominatim/OSRM calls.
      cwd: '..',
      env: {
        ...(process.env as Record<string, string>),
        ROUTE_FIXTURES: '1',
        // The app builds the Mapbox provider at import; fixtures mode never
        // calls it, so a placeholder keeps the suite hermetic.
        MAPBOX_TOKEN: process.env.MAPBOX_TOKEN ?? 'e2e-fixtures-token',
      },
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: 'npm run preview -- --port 5173 --strictPort',
      url: 'http://localhost:5173',
      // webServer.cwd is relative to this config's directory (frontend/), so
      // 'frontend' resolved to frontend/frontend and failed with
      // "spawn /bin/sh ENOENT". '.' is the frontend package root.
      cwd: '.',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
})
