import { expect, test } from '@playwright/test'

import { enableFixturesMode, setGeolocation } from './helpers'

/**
 * 042 map destination build flow.
 *
 * The map pick is the deliberate path: destination -> drawer -> preferences ->
 * Build route -> dimmed spinner -> route on the map. The typed-endpoint
 * auto-plan is covered by the 040/041 specs.
 */

test.use({ viewport: { width: 390, height: 844 } })

const REVERSE = {
  suggestions: [
    {
      id: 'map-pick-1',
      label: 'Angerlohe park',
      lat: 48.1642,
      lng: 11.6056,
      type: 'place',
      attribution: '© Mapbox',
    },
  ],
}

async function openBuilder(page: import('@playwright/test').Page): Promise<void> {
  await enableFixturesMode(page)
  await setGeolocation(page, 48.137, 11.575)
  await page.route('**/geocode/reverse**', (route) => route.fulfill({ json: REVERSE }))
  await page.goto('/')

  await page.locator('button[aria-label="Pick end on map"]').click()
  await page.locator('#map').click({ position: { x: 200, y: 300 } })
}

test('map destination opens the builder, Build route shows the spinner, then the route', async ({
  page,
}) => {
  let routeRequests = 0
  page.on('request', (request) => {
    if (request.url().includes('/route') && request.method() === 'POST') routeRequests += 1
  })

  await openBuilder(page)

  const drawer = page.locator('[data-testid="drawer"]')
  await expect(drawer).toHaveAttribute('data-open', 'true')
  await expect(page.locator('[data-testid="build-route"]')).toBeVisible()
  expect(routeRequests).toBe(0)

  // Parameters live behind the 041 sheet; applying keeps the builder open.
  await page.locator('[data-testid="prefs-edit"]').click()
  await expect(page.locator('[data-testid="prefs-sheet"]')).toBeVisible()

  // 042 AC-6: the locate control must be covered by the sheet scrim.
  const locateCovered = await page.evaluate(() => {
    const locate = document.querySelector('[data-testid="map-locate"]')
    if (!locate) return true
    const box = locate.getBoundingClientRect()
    const top = document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2)
    return !top || !(locate === top || locate.contains(top))
  })
  expect(locateCovered).toBe(true)

  await page.locator('[data-testid="prefs-sheet"] [data-testid="shade-more"]').click()
  await page.locator('[data-testid="prefs-apply"]').click()
  await expect(page.locator('[data-testid="prefs-sheet"]')).toBeHidden()
  await expect(drawer).toHaveAttribute('data-open', 'true')

  // Hold the route response so the spinner state is observable.
  await page.route('**/route', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 700))
    await route.continue()
  })

  await page.locator('[data-testid="build-route"]').click()
  await expect(drawer).toHaveAttribute('data-open', 'false')
  await expect(page.locator('[data-testid="route-loading"]')).toBeVisible()
  await expect(page.locator('[data-testid="route-loading"]')).toBeHidden({ timeout: 20000 })

  await expect(drawer).toHaveAttribute('data-open', 'false')
  await expect(page.locator('.leaflet-overlay-pane path')).not.toHaveCount(0)
  expect(routeRequests).toBe(1)

  // The compact result is still one handle away.
  await page.locator('[data-testid="drawer-handle"]').click()
  await expect(page.locator('section.route-summary .duration')).toBeVisible()
  await expect(page.locator('[data-testid="build-route"]')).toHaveCount(0)
})

test('a failed build dismisses the spinner and reopens the builder with the error', async ({
  page,
}) => {
  await openBuilder(page)

  await page.route('**/route', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 300))
    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'Routing failed' }),
    })
  })

  const drawer = page.locator('[data-testid="drawer"]')
  await page.locator('[data-testid="build-route"]').click()
  await expect(page.locator('[data-testid="route-loading"]')).toBeVisible()
  await expect(page.locator('[data-testid="route-loading"]')).toBeHidden({ timeout: 10000 })

  await expect(drawer).toHaveAttribute('data-open', 'true')
  await expect(drawer).toContainText('Routing failed')
  await expect(page.locator('[data-testid="build-route"]')).toBeVisible()
})
