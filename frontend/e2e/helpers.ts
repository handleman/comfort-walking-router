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
