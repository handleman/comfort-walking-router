import { test, expect } from '@playwright/test'

import { enableFixturesMode, planRoute, setGeolocation } from './helpers'

/**
 * 062: a deterministic desktop capture for the 90% visual gate.
 * The sidebar (not the live map) is the compared region; it carries the
 * endpoint card, comfort controls and route summary.
 */

test.use({ viewport: { width: 1280, height: 800 } })

test('desktop route state is captured for the visual gate', async ({ page }) => {
  await enableFixturesMode(page)
  await setGeolocation(page, 48.137, 11.575)
  await page.goto('/')

  const status = await planRoute(page, 'Marienplatz, Munich', 'Englischer Garten')
  expect(status).toBe(200)
  await expect(page.locator('[data-testid="sidebar"]')).toBeVisible()
  await expect(page.locator('section.route-summary').first()).toBeVisible()
  await page.waitForTimeout(500)
  await page.screenshot({ path: 'test-results/041-desktop-route.png' })
})
