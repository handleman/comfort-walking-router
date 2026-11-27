import { test, expect } from '@playwright/test'

import {
  chooseSuggestion,
  countRequestsMatching,
  enableFixturesMode,
  planRoute,
  setGeolocation,
} from './helpers'

// Preferences live in Postgres (spec 005, ADR-007); without DATABASE_URL the
// panel correctly shows an API error. That is a human gate, not a UI regression.
test.skip(!process.env.DATABASE_URL, 'prefs need Postgres (005 human gate)')

test('comfort panel exposes the shade segments and quieter switch', async ({ page }) => {
  await enableFixturesMode(page)
  await setGeolocation(page, 48.137, 11.575)
  await page.goto('/')

  const panel = page.locator('[data-testid="comfort-panel"]')
  await expect(panel).toBeVisible()

  await expect(panel.locator('[data-testid="shade-more"]')).toBeVisible()
  await expect(panel.locator('[data-testid="shade-balanced"]')).toBeVisible()
  await expect(panel.locator('[data-testid="shade-more-sun"]')).toBeVisible()
  await expect(panel.locator('[data-testid="quieter"]')).toBeVisible()

  // Desktop applies immediately: no Edit / Save buttons any more.
  await panel.locator('[data-testid="shade-more"]').click()
  await expect(panel.locator('[data-testid="shade-more"]')).toHaveAttribute('aria-pressed', 'true')
  await expect(panel.locator('[data-testid="shade-balanced"]')).toHaveAttribute(
    'aria-pressed',
    'false',
  )
})

test('shade More sun saves cloudy and is applied to the routed result', async ({ page }) => {
  await enableFixturesMode(page)
  await setGeolocation(page, 48.137, 11.575)
  await page.goto('/')

  const panel = page.locator('[data-testid="comfort-panel"]')
  await panel.locator('[data-testid="shade-more-sun"]').click()
  await expect(panel.locator('[data-testid="shade-more-sun"]')).toHaveAttribute(
    'aria-pressed',
    'true',
  )

  await planRoute(page, 'Marienplatz, Munich', 'Englischer Garten')

  const summary = page.locator('section.route-summary')
  await expect(summary).toBeVisible()
  await summary.getByText('Why this route?').click()
  await expect(summary.locator('ul.factors')).toBeVisible()
  await expect(summary.locator('ul.factors')).toContainText('cloud cover')
  await expect(summary.locator('ul.factors')).toContainText('Cloudy preference')
  await expect(page.locator('.comfort-legend')).toBeVisible()

  // Reset restores the balanced default for the next run.
  await panel.getByRole('button', { name: 'Reset' }).click()
  await expect(panel.locator('[data-testid="shade-balanced"]')).toHaveAttribute(
    'aria-pressed',
    'true',
  )
})

test('repeating an identical route query renders the cached result without a second external call', async ({
  page,
}) => {
  await enableFixturesMode(page)
  await setGeolocation(page, 48.137, 11.575)
  await page.goto('/')

  const routeRequestCount = countRequestsMatching(page, '/route')

  await planRoute(page, 'Marienplatz, Munich', 'Englischer Garten')

  await expect(page.locator('section.route-summary .duration')).toBeVisible()

  // Re-enter the same endpoints and re-select the same suggestions; the 040
  // auto-plan guard must not fire a second POST /route for the same pair.
  await chooseSuggestion(
    page,
    'input[placeholder="e.g. Marienplatz, Munich"]',
    'Marienplatz, Munich',
  )
  await chooseSuggestion(page, 'input[placeholder="e.g. Englischer Garten"]', 'Englischer Garten')

  await expect(page.locator('section.route-summary .duration')).toBeVisible()
  expect(routeRequestCount()).toBe(1)
})
