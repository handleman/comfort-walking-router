import type { Page } from '@playwright/test'

/**
 * Grant the given page's browser context geolocation permission and set a
 * fixed location so geolocation-dependent UI can be tested deterministically.
 */
export async function setGeolocation(
  page: Page,
  latitude: number,
  longitude: number,
): Promise<void> {
  await page.context().setGeolocation({ latitude, longitude, accuracy: 10 })
  await page.context().grantPermissions(['geolocation'])
}

/**
 * Enable route fixtures for the given page's browser context so the frontend
 * never makes live external calls during tests.
 */
export async function enableFixturesMode(page: Page): Promise<void> {
  await page.context().addInitScript(() => {
    ;(window as { __ROUTE_FIXTURES__?: number }).__ROUTE_FIXTURES__ = 1
  })
}

/**
 * Options for a spec that creates its own browser context: an empty storage
 * state so each context starts with no cookies or origin storage (isolation).
 */
export function freshContextOptions(): {
  storageState: { cookies: never[]; origins: never[] }
} {
  return { storageState: { cookies: [], origins: [] } }
}

/**
 * Fill both search inputs (origin and destination) using the canonical
 * placeholders rendered by TopSearchCard.svelte.
 */
export async function fillSearchInputs(
  page: Page,
  origin: string,
  destination: string,
): Promise<void> {
  await page.locator('input[placeholder="e.g. Marienplatz, Munich"]').fill(origin)
  await page.locator('input[placeholder="e.g. Englischer Garten"]').fill(destination)
}

/**
 * Count requests whose URL matches the given pattern (substring or RegExp)
 * as they fire on the page. Returns a getter for the running total so a spec
 * can assert on the count after the interaction under test.
 */
export function countRequestsMatching(page: Page, urlPattern: string | RegExp): () => number {
  let count = 0
  page.on('request', (request) => {
    const url = request.url()
    if (typeof urlPattern === 'string' ? url.includes(urlPattern) : urlPattern.test(url)) {
      count += 1
    }
  })
  return () => count
}

/**
 * Type into a search input and pick the first suggestion. The 040 auto-plan
 * needs a *selected* endpoint (not typed text), so a spec must choose one.
 */
export async function chooseSuggestion(
  page: Page,
  inputSelector: string,
  query: string,
): Promise<void> {
  await page.locator(inputSelector).fill(query)
  const option = page.locator('[role="option"]').first()
  await option.waitFor({ state: 'visible', timeout: 10000 })
  await option.click()
}

/**
 * Plan a route the 040 way: choose both suggestions; the app auto-fires
 * `POST /route` (there is no Find-route button). Returns the response status
 * so the spec never races the request.
 */
export async function planRoute(page: Page, origin: string, destination: string): Promise<number> {
  const response = page.waitForResponse(
    (r) => r.request().method() === 'POST' && r.url().includes('/route'),
  )
  // The first geolocation fix pre-fills the origin and closes any open
  // suggestion list: typing before it lands races the fix (flaky under
  // parallel workers). Wait for the pre-fill, but do not fail a spec that
  // deliberately has no fix.
  await page
    .waitForFunction(
      () =>
        (
          document.querySelector(
            'input[placeholder="e.g. Marienplatz, Munich"]',
          ) as HTMLInputElement | null
        )?.value !== '',
      undefined,
      { timeout: 10000 },
    )
    .catch(() => {})
  await chooseSuggestion(page, 'input[placeholder="e.g. Marienplatz, Munich"]', origin)
  await chooseSuggestion(page, 'input[placeholder="e.g. Englischer Garten"]', destination)
  return (await response).status()
}
