import { expect, test } from '@playwright/test'

import { enableFixturesMode, setGeolocation } from './helpers'

test('walk mode finds a route with fixtures and Munich geolocation', async ({ page }) => {
  await enableFixturesMode(page)
  await setGeolocation(page, 48.137, 11.575)
  await page.goto('/')

  await page.locator('input[placeholder="e.g. Marienplatz, Munich"]').fill('Marienplatz, Munich')
  await page.locator('input[placeholder="e.g. Englischer Garten"]').fill('Englischer Garten')
  await page.locator('button:has-text("Find route")').click()

  await expect(page.locator('.result')).toBeVisible()
})

test('walk mode shows a marker at the origin after starting navigation', async ({ page }) => {
  await enableFixturesMode(page)
  await setGeolocation(page, 48.137, 11.575)
  await page.goto('/')

  await page.locator('input[placeholder="e.g. Marienplatz, Munich"]').fill('Marienplatz, Munich')
  await page.locator('input[placeholder="e.g. Englischer Garten"]').fill('Englischer Garten')
  await page.locator('button:has-text("Find route")').click()
  await expect(page.locator('.result')).toBeVisible()

  await page.locator('button.walk-start').click()
  await expect(page.locator('.leaflet-marker-icon').first()).toBeVisible()
})

test('walk mode shows the reroute warning after drifting off route', async ({ page }) => {
  await enableFixturesMode(page)
  await setGeolocation(page, 48.137, 11.575)
  await page.goto('/')

  await page.locator('input[placeholder="e.g. Marienplatz, Munich"]').fill('Marienplatz, Munich')
  await page.locator('input[placeholder="e.g. Englischer Garten"]').fill('Englischer Garten')
  await page.locator('button:has-text("Find route")').click()
  await expect(page.locator('.result')).toBeVisible()

  await page.locator('button.walk-start').click()
  await expect(page.locator('.leaflet-marker-icon').first()).toBeVisible()

  // Simulate position ticks that drift the marker off the route.
  await setGeolocation(page, 48.15, 11.6)
  await setGeolocation(page, 48.16, 11.62)

  await expect(page.locator('.reroute-warning')).toContainText('Off route — reroute?')
})

test('walk mode shows the arrived banner after reaching the destination', async ({ page }) => {
  await enableFixturesMode(page)
  await setGeolocation(page, 48.137, 11.575)
  await page.goto('/')

  await page.locator('input[placeholder="e.g. Marienplatz, Munich"]').fill('Marienplatz, Munich')
  await page.locator('input[placeholder="e.g. Englischer Garten"]').fill('Englischer Garten')
  await page.locator('button:has-text("Find route")').click()
  await expect(page.locator('.result')).toBeVisible()

  await page.locator('button.walk-start').click()
  await expect(page.locator('.leaflet-marker-icon').first()).toBeVisible()

  // Simulate a final position fix at the destination (Englischer Garten).
  await setGeolocation(page, 48.155, 11.583)

  await expect(page.locator('.walk-arrived-banner')).toContainText('Arrived!')

  await page.locator('button.walk-stop').click()
  await expect(page.locator('.walk-arrived-banner')).toBeHidden()
  await expect(page.locator('button.walk-start')).toBeEnabled()
})
