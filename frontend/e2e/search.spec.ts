import { expect, test } from '@playwright/test'

import { enableFixturesMode, setGeolocation } from './helpers'

test('search page loads with fixtures and Munich geolocation', async ({ page }) => {
  await enableFixturesMode(page)
  await setGeolocation(page, 48.137, 11.575)
  await page.goto('/')

  await page.locator('input[placeholder="e.g. Marienplatz, Munich"]').fill('Marienplatz, Munich')
  await page.locator('input[placeholder="e.g. Englischer Garten"]').fill('Englischer Garten')
  await page.locator('button:has-text("Find route")').click()
})

test('a routed walk shows the OSM comfort data behind its score', async ({ page }) => {
  await enableFixturesMode(page)
  await setGeolocation(page, 48.137, 11.575)
  await page.goto('/')

  await page.locator('input[placeholder="e.g. Marienplatz, Munich"]').fill('Marienplatz, Munich')
  await page.locator('input[placeholder="e.g. Englischer Garten"]').fill('Englischer Garten')
  await page.locator('button:has-text("Find route")').click()

  // 001 AC-2: the explanation has to name the data it actually used. The
  // fixture corridor is 5 ways with 2 trees, so shade 0.60 / quiet 0.80.
  await expect(page.locator('.result')).toBeVisible()
  await expect(page.locator('.result')).toContainText('Comfort data: OSM corridor')
  await expect(page.locator('.result')).toContainText('shade 0.60')
  await expect(page.locator('.result')).toContainText('quiet 0.80')
})
