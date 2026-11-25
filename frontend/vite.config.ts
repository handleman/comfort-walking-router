import { configDefaults, defineConfig } from 'vitest/config'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import tailwindcss from '@tailwindcss/vite'

// The acceptance stand starts the API on a free port and exports this;
// the e2e config keeps :8000. A hardcoded target made every acceptance
// /geocode and /route call miss the server it had just started.
const backend = process.env.VITE_BACKEND_URL || 'http://localhost:8000'

// Every app API prefix. `server.proxy` covers `vite dev`; `preview` is a
// different server and does NOT inherit it, so the Playwright suite (which runs
// `vite preview`) was calling /route on :5173 and getting a 404 — no `.result`
// could ever appear.
const proxy = Object.fromEntries(
  ['/route', '/geocode', '/saved-routes'].map((path) => [
    path,
    { target: backend, changeOrigin: true },
  ]),
)

export default defineConfig({
  plugins: [tailwindcss(), svelte()],
  test: {
    exclude: [...configDefaults.exclude, 'e2e/**'],
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy,
  },
  preview: {
    port: 5173,
    strictPort: true,
    proxy,
  },
})
