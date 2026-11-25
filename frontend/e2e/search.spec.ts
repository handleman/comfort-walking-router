import { expect, test } from '@playwright/test'

import { enableFixturesMode, planRoute, setGeolocation } from './helpers'

test('search page loads with fixtures and Munich geolocation', async ({ page }) => {
  await enableFixturesMode(page)
  await setGeolocation(page, 48.137, 11.575)
  await page.goto('/')

  // Auto-plan (T16/AC-8): typing alone does not arm it — both endpoints must
  // be *selected suggestions*, so use planRoute and wait for the auto-fired
  // POST /route.
  const status = await planRoute(page, 'Marienplatz, Munich', 'Englischer Garten')
  expect(status).toBe(200)
  await expect(page.locator('section.route-summary')).toBeVisible()
})

test('a routed walk shows the OSM comfort data behind its score', async ({ page }) => {
  await enableFixturesMode(page)
  await setGeolocation(page, 48.137, 11.575)
  await page.goto('/')

  const status = await planRoute(page, 'Marienplatz, Munich', 'Englischer Garten')
  expect(status).toBe(200)
  await expect(page.locator('section.route-summary')).toBeVisible()

  // 001 AC-2: the explanation has to name the data it actually used. The
  // fixture corridor is 5 ways with 2 trees, so shade 0.60 / quiet 0.80.
  await expect(page.locator('section.route-summary')).toContainText('Comfort data: OSM corridor')
  await expect(page.locator('section.route-summary')).toContainText('shade 0.60')
  await expect(page.locator('section.route-summary')).toContainText('quiet 0.80')
})

test('a routed walk shows the comfort profile legend and bands', async ({ page }) => {
  await enableFixturesMode(page)
  await setGeolocation(page, 48.137, 11.575)
  await page.goto('/')

  // Auto-plan (T16/AC-8): typing alone does not arm it — both endpoints must
  // be *selected suggestions*, so use planRoute and wait for the auto-fired
  // POST /route.
  const status = await planRoute(page, 'Marienplatz, Munich', 'Englischer Garten')
  expect(status).toBe(200)
  await expect(page.locator('section.route-summary')).toBeVisible()

  await expect(page.locator('.comfort-legend')).toBeVisible()

  // 028 T5 AC-4: at least two distinct comfort-band classes must be present.
  const bandClasses = await page.locator('.comfort-band').evaluateAll((els) => {
    const seen = new Set<string>()
    for (const el of els) {
      for (const name of Array.from(el.classList)) {
        if (name !== 'comfort-band') seen.add(name)
      }
    }
    return Array.from(seen)
  })
  expect(bandClasses.length).toBeGreaterThan(1)

  // 028 T5 AC-5: one tooltip/label must show a `.../100` score.
  await expect(page.locator('.comfort-segments')).toContainText(/\/100/)
})
