import { test, expect } from '@playwright/test'

import { enableFixturesMode, planRoute, setGeolocation } from './helpers'

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

  // 040: auto-plan fires only when both endpoints are selected suggestions.
  const status = await planRoute(page, 'Marienplatz, Munich', 'Englischer Garten')
  expect(status).toBe(200)

  // 041: on mobile the results sheet auto-opens once a route exists — no
  // handle click needed. It stays toggleable through the handle.
  const drawer = page.locator('[data-testid="drawer"]')
  await expect(drawer).toHaveAttribute('data-open', 'true')
  await expect(drawer.locator('[data-testid="drawer-handle"]')).toHaveAttribute(
    'aria-expanded',
    'true',
  )

  // The results stay resolvable inside the open sheet.
  await expect(page.locator('section.route-summary')).toBeVisible()
  await expect(page.locator('section.route-summary .chip')).toBeVisible()
  await expect(page.locator('.comfort-segments').first()).toBeVisible()
  await expect(page.locator('[data-testid="drawer"] button.walk-start')).toBeVisible()

  // 041: starting the walk swaps the sheet's CTA for the stop control, which
  // must stay resolvable inside the sheet.
  await page.locator('[data-testid="drawer"] button.walk-start').click()
  await expect(page.locator('[data-testid="drawer"] button.walk-stop')).toBeVisible()

  await expect(page.locator('#map')).toBeVisible()
  await expect(page.locator('.leaflet-container')).toBeVisible()

  const overflow = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }))
  expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth)
})

test('a 400 planning failure surfaces its message and keeps the layout intact', async ({
  page,
}) => {
  // The API rejects a too-close pair with 400; the sheet stays closed and the
  // message renders without breaking the 390px layout.
  await page.route('**/route', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue()
      return
    }
    await route.fulfill({
      status: 400,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'Origin and destination are too close' }),
    })
  })

  await page.goto('/')

  const originInput = page.locator('input[placeholder="e.g. Marienplatz, Munich"]')
  const destinationInput = page.locator('input[placeholder="e.g. Englischer Garten"]')
  await expect(originInput).toBeVisible()
  await expect(originInput).toBeEnabled()
  await expect(destinationInput).toBeVisible()
  await expect(destinationInput).toBeEnabled()

  const status = await planRoute(page, 'Marienplatz, Munich', 'Englischer Garten')
  expect(status).toBe(400)

  // The 400 message is surfaced (attached, not necessarily on top of the map)
  // and no sheet opens without a route.
  await expect(page.getByText('Origin and destination are too close')).toBeAttached()
  await expect(page.locator('[data-testid="drawer"]')).toHaveAttribute('data-open', 'false')

  const overflow = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }))
  expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth)
})
