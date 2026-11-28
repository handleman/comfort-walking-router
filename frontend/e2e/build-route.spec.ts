import { test, expect, type Page } from '@playwright/test'

import { enableFixturesMode, setGeolocation } from './helpers'

/**
 * 042 AC-1..8: the mobile map-pick build flow.
 *
 * The map pick is fired through the fixtures-only `window.__map` hook; the
 * reverse geocode is fulfilled locally, and `/route` is held so the spinner is
 * observable. The success path also writes the two viewport screenshots the
 * 90 % visual gate (062) compares.
 */

const ORIGIN = { lat: 53.88672, lng: 27.51741 }
const DESTINATION = { lat: 53.891, lng: 27.52298 }

const START_INPUT = 'input[placeholder="e.g. Marienplatz, Munich"]'

async function reverse(page: Page, route: import('@playwright/test').Route) {
  const url = new URL(route.request().url())
  const lat = Number(url.searchParams.get('lat') ?? '0')
  const destination = Math.abs(lat - DESTINATION.lat) < 0.001
  await route.fulfill({
    json: {
      suggestions: [
        {
          id: destination ? 'dest-place' : 'origin-place',
          label: destination ? 'Destination place' : 'My location',
          lat: destination ? DESTINATION.lat : ORIGIN.lat,
          lng: destination ? DESTINATION.lng : ORIGIN.lng,
          type: 'place',
          attribution: '© Mapbox',
        },
      ],
    },
  })
}

async function openBuilder(page: Page) {
  await page.getByRole('button', { name: 'Pick end on map' }).click()
  await page.evaluate(({ lat, lng }) => {
    const map = (
      window as unknown as { __map?: { fire: (event: string, payload: unknown) => void } }
    ).__map
    if (!map) throw new Error('fixtures map hook is not available')
    map.fire('click', { latlng: { lat, lng } })
  }, DESTINATION)
  await expect(page.locator('[data-testid="route-builder"]')).toBeVisible()
  await expect(page.locator('[data-testid="drawer"]')).toHaveAttribute('data-open', 'true')
  // Let the 250 ms sheet transition finish before the viewport screenshot.
  await page.waitForTimeout(350)
}

test.use({ viewport: { width: 390, height: 844 } })

test.beforeEach(async ({ page }) => {
  await enableFixturesMode(page)
  await setGeolocation(page, ORIGIN.lat, ORIGIN.lng)
  await page.route('**/geocode/reverse**', (route) => reverse(page, route))
})

test('map pick opens the builder and Build route owns the request', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  let routeRequests = 0
  let release!: () => void
  const held = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route('**/route', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue()
      return
    }
    routeRequests += 1
    await held
    await route.continue()
  })

  await page.goto('/')
  await expect(page.locator(START_INPUT)).not.toHaveValue('')

  await openBuilder(page)
  await expect(page.getByText('Destination place')).toBeVisible()
  await expect(page.locator('[data-testid="build-route"]')).toHaveCSS(
    'background-color',
    'rgb(23, 118, 92)',
  )
  // AC-1: the map pick parks the planner; no request before the pill.
  expect(routeRequests).toBe(0)

  await page.screenshot({ path: 'test-results/042-builder-mobile.png' })

  // AC-2: Edit opens the styled preferences sheet; closing keeps the builder.
  await page.getByRole('button', { name: 'Edit' }).click()
  await expect(page.locator('[data-testid="prefs-sheet"]')).toBeVisible()
  await page.locator('[data-testid="prefs-close"]').click()
  await expect(page.locator('[data-testid="route-builder"]')).toBeVisible()

  await page.locator('[data-testid="build-route"]').click()
  await expect(page.locator('[data-testid="route-loading"]')).toBeVisible()
  await expect(page.locator('[data-testid="route-loading"]')).toHaveAttribute('role', 'status')
  await expect(page.locator('[data-testid="drawer"]')).toHaveAttribute('data-open', 'false')
  await expect(page.locator('[data-testid="route-loading"]')).toHaveCSS('opacity', '1')
  await expect(page.locator('.route-loading-spinner')).toHaveCSS(
    'background-color',
    'rgb(255, 255, 255)',
  )
  await page.waitForTimeout(300)
  // AC-3: the dimmed overlay really covers the viewport.
  const box = await page.locator('[data-testid="route-loading"]').boundingBox()
  expect(box?.width).toBe(390)
  expect(box?.height).toBe(844)
  await page.screenshot({ path: 'test-results/042-spinner-mobile.png' })

  release()
  await expect(page.locator('[data-testid="route-loading"]')).toHaveCount(0)
  // AC-4: success leaves the drawer closed and draws the route.
  await expect(page.locator('[data-testid="drawer"]')).toHaveAttribute('data-open', 'false')
  await expect(page.locator('.leaflet-overlay-pane path').first()).toBeVisible()

  // Opening the drawer shows the compact summary.
  await page.locator('[data-testid="drawer-handle"]').click()
  await expect(page.locator('[data-testid="drawer"]')).toHaveAttribute('data-open', 'true')
  await expect(page.locator('section.route-summary')).toBeVisible()
  await page.waitForTimeout(350)
  await page.screenshot({ path: 'test-results/042-route-mobile.png' })
})

test('a 500 dismisses the overlay and reopens the builder with the error', async ({ page }) => {
  await page.route('**/route', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue()
      return
    }
    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'Route planning failed (500)' }),
    })
  })

  await page.goto('/')
  await openBuilder(page)
  await page.locator('[data-testid="build-route"]').click()

  await expect(page.locator('[data-testid="route-loading"]')).toHaveCount(0)
  await expect(page.locator('[data-testid="drawer"]')).toHaveAttribute('data-open', 'true')
  await expect(page.locator('[data-testid="build-error"]')).toContainText('500')
  await expect(page.locator('.leaflet-overlay-pane path')).toHaveCount(0)
})
