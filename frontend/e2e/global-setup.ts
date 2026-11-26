import { execSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

/**
 * 054 AC-1: every e2e entry point builds first.
 *
 * `npx playwright test` serves `frontend/dist/` through `vite preview` and does
 * not rebuild it. On 2026-11-26 a source edit appeared in no run for ~40 minutes
 * (and an unchanged app can be marked green) because the suite was exercising
 * the previous build. Building here covers the raw command, the npm script and
 * `swarm.e2e`, so a stale `dist/` is no longer a possible signal.
 */
export default function globalSetup(): void {
  const frontend = fileURLToPath(new URL('..', import.meta.url))
  execSync('npm run build', { cwd: frontend, stdio: 'inherit' })
}
