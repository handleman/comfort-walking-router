import { test, expect } from '@playwright/test'

import {
  chooseSuggestion,
  countRequestsMatching,
  enableFixturesMode,
  planRoute,
  setGeolocation,
} from './helpers'

// Preferences live in Postgres (spec 005, ADR-007); without DATABASE_URL the
// panel correctly shows an API error. That is a human gate, not a UI regression.
test.skip(!process.env.DATABASE_URL, 'prefs need Postgres (005 human gate)')

test('preferences panel shows the default_preference select', async ({ page }) => {
  await enableFixturesMode(page)
  await setGeolocation(page, 48.137, 11.575)
  await page.goto('/')

  await page.getByRole('button', { name: 'Edit preferences' }).click()
  await expect(page.locator('.prefs select')).toBeVisible()
})

test('saved cloudy default_preference is applied to the routed result', async ({ page }) => {
  await enableFixturesMode(page)
  await setGeolocation(page, 48.137, 11.575)
  await page.goto('/')

  await page.getByRole('button', { name: 'Edit preferences' }).click()
  await page.locator('.prefs select').selectOption('cloudy')
  await page.getByRole('button', { name: 'Save preferences' }).click()

  await planRoute(page, 'Marienplatz, Munich', 'Englischer Garten')

  await expect(page.locator('section.route-summary .chip')).toContainText('cloudy')
  await expect(page.locator('section.route-summary ul.factors')).toBeVisible()
  await expect(page.locator('section.route-summary ul.factors')).toContainText('cloud cover')
})

test('repeating an identical route query renders the cached result without a second external call', async ({
  page,
}) => {
  await enableFixturesMode(page)
  await setGeolocation(page, 48.137, 11.575)
  await page.goto('/')

  const routeRequestCount = countRequestsMatching(page, '/route')

  await planRoute(page, 'Marienplatz, Munich', 'Englischer Garten')

  await expect(page.locator('section.route-summary .chip')).toBeVisible()

  // Re-enter the same endpoints and re-select the same suggestions; the 040
  // auto-plan guard must not fire a second POST /route for the same pair.
  await chooseSuggestion(
    page,
    'input[placeholder="e.g. Marienplatz, Munich"]',
    'Marienplatz, Munich',
  )
  await chooseSuggestion(page, 'input[placeholder="e.g. Englischer Garten"]', 'Englischer Garten')

  await expect(page.locator('section.route-summary .chip')).toBeVisible()
  expect(routeRequestCount()).toBe(1)
})
