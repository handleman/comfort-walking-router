import { expect, test } from '@playwright/test'

import { enableFixturesMode, setGeolocation } from './helpers'

// Spec 014, T10 (AC-8/AC-9): the attribution credit (provider + OSM) is shown
// wherever a suggestion/route is displayed. The stubbed body mirrors the real
// /geocode contract (contracts/geocode.json: Suggestion requires
// id, label, lat, lng, type, attribution).
test('walk guidance shows the geocoder attribution for the picked suggestion', async ({ page }) => {
  await enableFixturesMode(page)
  await setGeolocation(page, 48.137, 11.575)

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

  await page.locator('input[placeholder="e.g. Marienplatz, Munich"]').fill('Marienplatz, Munich')
  await page.locator('.suggestion').first().click()

  await page.locator('input[placeholder="e.g. Englischer Garten"]').fill('Englischer Garten')
  await page.locator('button:has-text("Find route")').click()

  await expect(page.locator('.result')).toBeVisible()
  await expect(page.locator('.attribution')).toBeVisible()
  await expect(page.locator('.attribution')).toContainText('Mapbox')
})
