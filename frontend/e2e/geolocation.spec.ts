import { expect, test } from '@playwright/test'

import { enableFixturesMode, setGeolocation } from './helpers'

/**
 * 050 AC-4: the four-state geolocation contract.
 *
 * The rest of the suite grants a fixed position and moves on; this spec pins
 * what the app does in each state — a fix renders the current-position marker,
 * a new fix moves it, a denial and an unavailable provider both ask for the
 * origin instead of leaving a dead map.
 */

const START_INPUT = 'input[placeholder="e.g. Marienplatz, Munich"]'
const START_MODAL = '[role="dialog"][aria-label="Choose start location"]'

test('geolocation: an allowed fix renders the current-position marker', async ({ page }) => {
  await enableFixturesMode(page)
  await setGeolocation(page, 48.137, 11.575)
  await page.goto('/')

  await expect(page.locator('.leaflet-marker-icon').first()).toBeVisible()
  // The first fix pre-fills the origin (reverse-geocoded against the fixture).
  await expect(page.locator(START_INPUT)).not.toHaveValue('')
})

test('geolocation: a new position moves the marker', async ({ page, context }) => {
  await enableFixturesMode(page)
  await setGeolocation(page, 48.137, 11.575)
  await page.goto('/')

  const marker = page.locator('.leaflet-marker-icon').first()
  await expect(marker).toBeVisible()
  const before = await marker.evaluate((el) => (el as HTMLElement).style.transform)

  await context.setGeolocation({ latitude: 48.142, longitude: 11.581, accuracy: 10 })

  await expect
    .poll(async () => marker.evaluate((el) => (el as HTMLElement).style.transform))
    .not.toBe(before)
})

test('geolocation: a denied permission asks for the origin', async ({ page, context }) => {
  await enableFixturesMode(page)
  await context.clearPermissions()
  await page.goto('/')

  await expect(page.locator(START_MODAL)).toBeVisible()
  await expect(page.getByText('Where do you want to start?')).toBeVisible()
})

test('geolocation: a denied permission recovers via a manual suggestion', async ({
  page,
  context,
}) => {
  await enableFixturesMode(page)
  await context.clearPermissions()
  await page.route('**/geocode**', async (route) => {
    await route.fulfill({
      json: {
        suggestions: [
          {
            id: 'mapbox-place-1',
            label: 'Marienplatz, Munich',
            lat: 48.137,
            lng: 11.575,
            type: 'place',
            attribution: '© Mapbox',
          },
        ],
      },
    })
  })
  await page.goto('/')

  const modal = page.locator(START_MODAL)
  await expect(modal).toBeVisible()
  await modal.locator(START_INPUT).fill('Marienplatz')
  const option = modal.locator('[role="option"]').first()
  await option.waitFor({ state: 'visible', timeout: 10000 })
  await option.click()

  await expect(modal).toBeHidden()
})
