import { test, expect } from '@playwright/test'

import { enableFixturesMode, setGeolocation } from './helpers'

/** 044: both endpoint fields search inside the geolocation's city/country. */

test.use({ viewport: { width: 390, height: 844 } })

test('autocomplete carries the geolocation country and city bbox', async ({ page }) => {
  const seen: string[] = []
  await page.route('**/geocode/context**', async (route) => {
    await route.fulfill({
      json: {
        country: 'Belarus',
        country_code: 'BY',
        city: 'Minsk',
        bbox: [27.373281, 53.79213, 27.790498, 53.97125],
        source: 'place',
      },
    })
  })
  await page.route('**/geocode/reverse**', async (route) => {
    await route.fulfill({
      json: {
        suggestions: [
          {
            id: 'origin',
            label: 'My location',
            lat: 53.88672,
            lng: 27.51741,
            type: 'place',
            attribution: '© Mapbox',
          },
        ],
      },
    })
  })
  await page.route(/\/geocode\?/, async (route) => {
    seen.push(route.request().url())
    await route.fulfill({
      json: {
        suggestions: [
          {
            id: 'local',
            label: 'Vulica Lienina, Minsk',
            lat: 53.891,
            lng: 27.55,
            type: 'address',
            attribution: '© Mapbox',
          },
        ],
      },
    })
  })

  await enableFixturesMode(page)
  await setGeolocation(page, 53.88672, 27.51741)
  await page.goto('/')

  await expect(page.getByTestId('search-scope')).toContainText('Minsk')
  const dest = page.getByTestId('dest-input')
  await dest.locator('input').fill('Lien')
  const option = dest.getByRole('option', { name: /Vulica Lienina/ }).first()
  await option.waitFor({ state: 'visible', timeout: 10000 })

  const query = seen.find((url) => url.includes('q=Lien'))
  expect(query).toBeTruthy()
  const url = new URL(query as string)
  expect(url.searchParams.get('country')).toBe('BY')
  expect(url.searchParams.get('bbox')).toBe('27.373281,53.79213,27.790498,53.97125')
})
