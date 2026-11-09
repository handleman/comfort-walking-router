import { test } from '@playwright/test'

import { enableFixturesMode, setGeolocation } from './helpers'

test('search page loads with fixtures and Munich geolocation', async ({ page }) => {
  await enableFixturesMode(page)
  await setGeolocation(page, 48.137, 11.575)
  await page.goto('/')

  await page.locator('input[placeholder="e.g. Marienplatz, Munich"]').fill('Marienplatz, Munich')
  await page.locator('input[placeholder="e.g. Englischer Garten"]').fill('Englischer Garten')
  await page.locator('button:has-text("Find route")').click()
})
