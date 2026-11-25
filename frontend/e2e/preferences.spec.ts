import { test, expect } from '@playwright/test'

import { enableFixturesMode, countRequestsMatching, planRoute, setGeolocation } from './helpers'

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

  await expect(page.locator('.route-summary .chip')).toContainText('cloudy')
  await expect(page.locator('.route-summary ul.factors')).toBeVisible()
  await expect(page.locator('.route-summary ul.factors')).toContainText('cloud cover')
})

test('auto-plan fires exactly one /route for a set of endpoints', async ({ page }) => {
  await enableFixturesMode(page)
  await setGeolocation(page, 48.137, 11.575)
  await page.goto('/')

  const routeRequestCount = countRequestsMatching(page, '/route')

  await planRoute(page, 'Marienplatz, Munich', 'Englischer Garten')

  await expect(page.locator('.route-summary .chip')).toBeVisible()
  // The auto-plan dedupes an identical endpoint pair: one POST /route.
  expect(routeRequestCount()).toBe(1)
})
