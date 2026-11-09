import { test, expect } from '@playwright/test'

import { enableFixturesMode, setGeolocation } from './helpers'

test.use({ viewport: { width: 390, height: 844 } })

test.beforeEach(async ({ page }) => {
  await enableFixturesMode(page)
  await setGeolocation(page, 48.137, 11.575)
})

test('search page is usable at 390px with no horizontal overflow', async ({ page }) => {
  await enableFixturesMode(page)
  await setGeolocation(page, 48.137, 11.575)
  await page.goto('/')

  const originInput = page.locator('input[placeholder="e.g. Marienplatz, Munich"]')
  const destinationInput = page.locator('input[placeholder="e.g. Englischer Garten"]')
  await expect(originInput).toBeVisible()
  await expect(originInput).toBeEnabled()
  await expect(destinationInput).toBeVisible()
  await expect(destinationInput).toBeEnabled()

  await originInput.fill('Marienplatz, Munich')
  await destinationInput.fill('Englischer Garten')
  await page.locator('button:has-text("Find route")').click()

  await expect(page.locator('#map')).toBeVisible()
  await expect(page.locator('.leaflet-container')).toBeVisible()

  const overflow = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }))
  expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth)
})
