import { test, expect } from '@playwright/test'

import { enableFixturesMode, countRequestsMatching, setGeolocation } from './helpers'

test('preferences panel shows the default_preference select', async ({ page }) => {
  await enableFixturesMode(page)
  await setGeolocation(page, 48.137, 11.575)
  await page.goto('/')

  await page.getByRole('button', { name: 'Edit preferences' }).click()
  await expect(page.locator('select')).toBeVisible()
})

test('saved cloudy default_preference is applied to the routed result', async ({ page }) => {
  await enableFixturesMode(page)
  await setGeolocation(page, 48.137, 11.575)
  await page.goto('/')

  await page.getByRole('button', { name: 'Edit preferences' }).click()
  await page.locator('.prefs select').selectOption('cloudy')
  await page.getByRole('button', { name: 'Save preferences' }).click()

  await page.locator('input[placeholder="e.g. Marienplatz, Munich"]').fill('Marienplatz, Munich')
  await page.locator('input[placeholder="e.g. Englischer Garten"]').fill('Englischer Garten')
  await page.locator('button:has-text("Find route")').click()

  await expect(page.locator('.result .chip')).toContainText('cloudy')
  await expect(page.locator('.result ul.factors')).toBeVisible()
  await expect(page.locator('.result ul.factors')).toContainText('cloud cover')
})

test('repeating an identical route query renders the cached result without a second external call', async ({
  page,
}) => {
  await enableFixturesMode(page)
  await setGeolocation(page, 48.137, 11.575)
  await page.goto('/')

  const routeRequestCount = countRequestsMatching(page, '/route')

  await page.locator('input[placeholder="e.g. Marienplatz, Munich"]').fill('Marienplatz, Munich')
  await page.locator('input[placeholder="e.g. Englischer Garten"]').fill('Englischer Garten')
  await page.locator('button:has-text("Find route")').click()

  await expect(page.locator('.result .chip')).toBeVisible()

  await page.locator('button:has-text("Find route")').click()

  await expect(page.locator('.result .chip')).toBeVisible()
  expect(routeRequestCount()).toBe(1)
})
