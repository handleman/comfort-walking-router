#!/usr/bin/env node
/** Spec acceptance browser runner (043).

One Node process driven by a JSON plan (`plan.json`):
* launch Chromium with geolocation granted and `__ROUTE_FIXTURES__=1`
* resize to desktop + mobile viewports, screenshot
* run deterministic checks per spec/AC
* emit one JSON document with shots, views (global facts), checks (per-AC results)

This is the only Playwright dependency in the harness; Python stays model-only.
*/

import { chromium } from 'playwright'
import { mkdirSync, readFileSync } from 'fs'
import { resolve } from 'path'

const PLAN_FILE = process.argv[2]
if (!PLAN_FILE) {
  console.error('usage: acceptance.mjs <plan.json>')
  process.exit(1)
}

const plan = JSON.parse(readFileSync(PLAN_FILE, 'utf-8'))
const baseUrl = plan.baseUrl
const outDir = plan.outDir
const views = plan.views || []
const checks = plan.checks || []
const layoutSpecs = plan.layout || []

mkdirSync(outDir, { recursive: true })

const screenshots = {}
const viewFacts = {}
const checkResults = []
const selftest = []
const layoutFacts = {}

const browser = await chromium.launch({
  headless: true,
  args: ['--no-sandbox', '--disable-setuid-sandbox'],
})

const context = await browser.newContext({
  geolocation: { latitude: 48.137, longitude: 11.575, accuracy: 10 },
  permissions: ['geolocation'],
  viewport: { width: 1280, height: 800 },
})

await context.addInitScript(() => {
  window.__ROUTE_FIXTURES__ = 1
})

const page = await context.newPage()

/** @type {string[]} */
const consoleErrors = []
page.on('console', (msg) => {
  if (msg.type() !== 'error') return
  // The browser logs *any* 5xx resource as a console error. A deliberate 503
  // from an optional feature (saved routes with no database, by 005's design)
  // is not a regression: uncaught exceptions and app-thrown console.error are.
  if (/Failed to load resource/i.test(msg.text())) return
  consoleErrors.push(msg.text())
})

page.on('pageerror', (err) => {
  consoleErrors.push(err.message)
})

let routeRequests = 0
page.on('request', (req) => {
  if (req.url().includes('/route')) routeRequests++
})

async function go(url) {
  await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 })
  await page.waitForTimeout(500)
}

/** Fill a combobox and click the suggestion that matches the typed text. */
async function pickSuggestion(input, text) {
  await page.fill(input, text)
  // Match the first word, not the whole typed string: live geocoders insert
  // a postal code ("Marienplatz, 80331 Munich, Germany"), while fixtures echo
  // the query exactly. Scoping to this input's combobox avoids the other
  // input's list; the hint avoids a stale list from this input's last query.
  const hint =
    String(text)
      .split(/[,\s]+/)
      .filter(Boolean)[0] || String(text)
  const option = page
    .locator('.search-combobox', { has: page.locator(input) })
    .locator('[role="option"]', { hasText: hint })
    .first()
  await option.waitFor({ state: 'visible', timeout: 8000 })
  await option.click()
  await page.waitForTimeout(300)
}

async function evaluateView(name, width, height) {
  await page.setViewportSize({ width, height })
  await page.waitForTimeout(300)

  const shotPath = resolve(outDir, `${name}.png`)
  await page.screenshot({ path: shotPath, fullPage: true })
  screenshots[name] = shotPath

  const facts = await page.evaluate(() => {
    const tiles = document.querySelectorAll('.leaflet-tile')
    const leaflet = document.querySelector('.leaflet-container')
    const buttons = Array.from(document.querySelectorAll('button, [role="button"]'))
      .filter((el) => el.offsetParent !== null)
      .map((el) => ({
        text: (el.textContent || '').trim().slice(0, 80),
        tag: el.tagName.toLowerCase(),
        class: el.className,
        visible: el.offsetWidth > 0 && el.offsetHeight > 0,
      }))
    const duplicates = buttons
      .filter((b) => b.visible)
      .reduce((acc, b) => {
        const key = b.text || b.class || b.tag
        acc[key] = (acc[key] || 0) + 1
        return acc
      }, {})
    const dupList = Object.entries(duplicates)
      .filter(([, c]) => c > 1)
      .map(([text]) => text)

    // 043/052: a control the user cannot hit is a defect — but an element that
    // is display:none / visibility:hidden (or inside an aria-hidden container)
    // is hidden by design, not zero-sized. Name the offenders for the report.
    const hiddenByAncestor = (el) => {
      // The mobile drawer's handle is 0x0 on desktop because an ancestor is
      // display:none; that is hidden by design, not an unhittable control.
      for (let node = el; node; node = node.parentElement) {
        const style = window.getComputedStyle(node)
        if (style.display === 'none' || style.visibility === 'hidden') return true
      }
      return !!el.closest('[hidden], [aria-hidden="true"]')
    }
    const zeroSizeElements = Array.from(
      document.querySelectorAll('button, a, input, [role="button"]'),
    ).filter((el) => {
      if (hiddenByAncestor(el)) return false
      return el.offsetWidth === 0 || el.offsetHeight === 0
    })
    const zeroSize = zeroSizeElements.length
    const zeroSizeNames = zeroSizeElements.map(
      (el) => `${el.tagName.toLowerCase()}${el.id ? '#' + el.id : ''}.${el.className || ''}`,
    )

    const overflow = document.documentElement.scrollWidth > document.documentElement.clientWidth

    return {
      tiles: tiles.length,
      leaflet: !!leaflet,
      duplicateButtons: dupList,
      zeroSize,
      zeroSizeNames,
      overflow,
      routeRequests: 0,
    }
  })

  facts.routeRequests = routeRequests
  routeRequests = 0
  viewFacts[name] = facts

  // 052: geometry + control presence, deterministic and DOM-only.
  if (layoutSpecs.length) {
    const measured = await page.evaluate((specs) => {
      const out = {}
      // NB: `offsetParent` is null for position:fixed elements (#map and the
      // bottom drawer are fixed), so it must not gate visibility here.
      const visibleOf = (el) => {
        const r = el.getBoundingClientRect()
        const cs = getComputedStyle(el)
        return (
          r.width > 0 &&
          r.height > 0 &&
          cs.display !== 'none' &&
          cs.visibility !== 'hidden' &&
          Number(cs.opacity || 1) > 0
        )
      }
      const rect = (el) => {
        const r = el.getBoundingClientRect()
        return {
          x: r.x + window.scrollX,
          y: r.y + window.scrollY,
          w: r.width,
          h: r.height,
          visible: visibleOf(el),
        }
      }
      for (const spec of specs) {
        const regions = {}
        const controls = {}
        const peers = []
        for (const [id, sel] of Object.entries(spec.regions || {})) {
          const el = document.querySelector(sel)
          if (el) regions[id] = rect(el)
        }
        for (const [id, sel] of Object.entries(spec.controls || {})) {
          const els = Array.from(document.querySelectorAll(sel)).filter((el) => visibleOf(el))
          const el = els[0]
          controls[id] = el ? { ...rect(el), count: els.length } : { visible: false, count: 0 }
          if (el) peers.push([id, el])
        }
        const overlaps = []
        for (let i = 0; i < peers.length; i++) {
          for (let j = i + 1; j < peers.length; j++) {
            const [ia, ea] = peers[i]
            const [ib, eb] = peers[j]
            if (ea.contains(eb) || eb.contains(ea)) continue // ancestors are allowed to contain
            const a = ea.getBoundingClientRect()
            const b = eb.getBoundingClientRect()
            const ix = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left))
            const iy = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top))
            if (ix * iy > 0) overlaps.push(`${ia}~${ib}`)
          }
        }
        out[spec.spec] = {
          regions,
          controls,
          overlaps,
          overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
        }
      }
      return out
    }, layoutSpecs)
    layoutFacts[name] = Object.values(measured)[0] || {}
  }
}

async function runOne(check, viewName) {
  const { kind, selector, expect, value, origin } = check
  const view = views.find((v) => v.name === viewName)
  if (!view) return null
  await page.setViewportSize({ width: view.width, height: view.height })
  await page.waitForTimeout(200)
  if (check.url) {
    await page.goto(check.url, { waitUntil: 'networkidle', timeout: 90000 })
    await page.waitForTimeout(500)
  }

  let ok = false
  let detail = ''

  try {
    switch (kind) {
      case 'exists': {
        const count = await page.locator(selector).count()
        ok = count > 0
        detail = ok ? `found ${count} element(s)` : 'not found'
        break
      }
      case 'absent': {
        const count = await page.locator(selector).count()
        ok = count === 0
        detail = ok ? 'absent' : `found ${count} element(s)`
        break
      }
      case 'count': {
        const count = await page.locator(selector).count()
        ok = count === Number(expect)
        detail = `count ${count} vs expect ${expect}`
        break
      }
      case 'min_count': {
        const count = await page.locator(selector).count()
        ok = count >= Number(expect)
        detail = `count ${count} >= ${expect}`
        break
      }
      case 'text': {
        const text = (await page.locator(selector).textContent()) || ''
        ok = String(text).includes(String(expect))
        detail = ok ? `text matches` : `text "${text.slice(0, 100)}" missing "${expect}"`
        break
      }
      case 'value_set': {
        const val = await page.locator(selector).inputValue()
        ok = val === String(value)
        detail = ok ? `value set` : `value "${val}" != "${value}"`
        break
      }
      case 'click': {
        await page.locator(selector).click()
        ok = true
        detail = 'clicked'
        break
      }
      case 'wait_for': {
        await page.locator(selector).waitFor({ state: 'visible', timeout: 10000 })
        ok = true
        detail = 'visible'
        break
      }
      case 'select': {
        await page.selectOption(selector, String(value))
        ok = true
        detail = `selected ${value}`
        break
      }
      case 'no_match': {
        const needle = String(value)
        const found = await page.evaluate((n) => {
          const html = document.documentElement.outerHTML
          const resources = performance.getEntriesByType('resource').map((entry) => entry.name)
          return html.includes(n) || resources.some((url) => url.includes(n))
        }, needle)
        ok = !found
        detail = ok ? `"${needle}" absent` : `"${needle}" present`
        break
      }
      case 'location_denied': {
        await context.clearPermissions()
        try {
          await go(check.url || baseUrl)
          await page.waitForTimeout(1500)
          const dialog = page.locator("[role='dialog'][aria-label='Choose start location']")
          ok = (await dialog.count()) > 0
          detail = ok
            ? 'start-location dialog shown on denied geolocation'
            : 'no dialog after denying geolocation'
        } finally {
          await context.grantPermissions(['geolocation'])
          await go(check.url || baseUrl)
        }
        break
      }
      case 'geo_step': {
        const markerStyle = () =>
          page.locator(selector).evaluate((el) => el.getAttribute('style') || '')
        const before = await markerStyle()
        const [dlat, dlng] = String(value || '0.001,0.001')
          .split(',')
          .map(Number)
        await context.setGeolocation({
          latitude: 48.137 + dlat,
          longitude: 11.575 + dlng,
          accuracy: 10,
        })
        await page.waitForTimeout(1500)
        const after = await markerStyle()
        ok = before !== after
        detail = ok
          ? 'marker moved after a new geolocation fix'
          : 'marker style unchanged after a fix'
        break
      }
      case 'live_route': {
        // Live lane: the real provider answers with distance/time. Waits for
        // the response (a live OSM corridor can take tens of seconds).
        const ORIGIN = "input[placeholder='e.g. Marienplatz, Munich']"
        const originText = origin || 'Marienplatz, Munich'
        await page.waitForTimeout(500)
        if (await page.locator(ORIGIN).count()) {
          await pickSuggestion(ORIGIN, originText)
          await page.waitForTimeout(1000)
        }
        // Attach a catch immediately: if the pick below fails, the pending
        // promise must not reject unhandled when the browser closes.
        const pending = page
          .waitForResponse(
            (res) => res.url().includes('/route') && res.request().method() === 'POST',
            { timeout: 180000 },
          )
          .catch(() => null)
        await pickSuggestion(selector, value)
        const response = await pending
        if (!response) {
          ok = false
          detail = 'no /route response (the destination suggestion was not selected)'
          break
        }
        const body = await response.json().catch(() => null)
        ok = Boolean(
          response.ok() && body && Number(body.distance_m) > 0 && Number(body.duration_s) > 0,
        )
        detail = ok
          ? `${Math.round(body.distance_m)} m / ${Math.round(body.duration_s)} s`
          : `${response.status()} ${JSON.stringify(body).slice(0, 140)}`
        break
      }
      case 'console_errors': {
        const limit = Number(expect ?? 0)
        ok = consoleErrors.length <= limit
        detail = ok
          ? `${consoleErrors.length} console error(s)`
          : `${consoleErrors.length} console error(s): ${consoleErrors.slice(0, 3).join(' | ')}`
        break
      }
      case 'route_request': {
        // 040: auto-plan arms only when BOTH endpoints are *selected*
        // suggestions — typing alone never fires POST /route. Use the same
        // flow as the e2e helper (fill, pick the first option), then wait for
        // the request. The old fill-and-wait check could never pass.
        const ORIGIN = "input[placeholder='e.g. Marienplatz, Munich']"
        const originText = origin || 'Marienplatz, Munich'
        // Let the first geolocation fix pre-fill the origin, then overwrite it.
        await page.waitForTimeout(500)
        // A geolocation fix already counts as a selected origin; overwrite an
        // editable input only when it is rendered.
        if (await page.locator(ORIGIN).count()) {
          await pickSuggestion(ORIGIN, originText)
          // Overwriting an origin that already has a destination makes the app
          // plan against the old pair; let that settle so the assertion below
          // is about the destination pick that follows.
          await page.waitForTimeout(1000)
        }
        routeRequests = 0
        await pickSuggestion(selector, value)
        const deadline = Date.now() + 8000
        while (routeRequests === 0 && Date.now() < deadline) {
          await page.waitForTimeout(100)
        }
        ok = routeRequests > 0
        detail = ok ? '/route request fired' : 'no /route request'
        break
      }
    }
  } catch (e) {
    ok = false
    detail = `error: ${e.message}`
  }
  return { ok, detail }
}

async function runCheck(check) {
  const { spec, ac, kind, selector, viewport } = check
  const targets = viewport === 'both' ? views.map((v) => v.name) : [viewport]
  for (const viewName of targets) {
    const result = await runOne(check, viewName)
    if (!result) continue
    checkResults.push({ spec, ac, kind, selector, viewport: viewName, ...result })
  }
}

/**
 * 054 AC-3: prove the oracle can fail.
 *
 * A check that passes after its target is removed is not testing anything (the
 * `.error` placeholder and the aria-label checks did exactly that for days). The
 * mutation is deliberately simple and reversible by reloading the page:
 *   selector checks  → remove every node the selector matches, re-run, expect fail
 *   route_request    → remove the destination input, re-run, expect an error
 *   console_errors   → inject a console.error, re-run, expect fail
 *   absent / count=0 → unsupported (there is nothing to remove); reported, not failed
 */
async function runSelftest(check) {
  const { spec, ac, kind, selector, expect } = check
  const verdict = { spec, ac, kind, selector, verdict: 'unsupported', detail: '' }
  if (
    kind === 'wait_for' ||
    kind === 'no_match' ||
    kind === 'live_route' ||
    kind === 'location_denied' ||
    kind === 'geo_step'
  ) {
    verdict.detail = 'no reversible mutation'
    return verdict
  }
  if (kind === 'absent' || (kind === 'count' && Number(expect) === 0)) {
    verdict.detail = 'nothing to remove (absent/count=0)'
    return verdict
  }
  await go(baseUrl)
  if (kind === 'console_errors') {
    await page.evaluate(() => console.error('acceptance selftest'))
    const result = await runOne(check, 'desktop')
    verdict.verdict = result && result.ok === false ? 'ok' : 'always_passes'
    verdict.detail = result ? result.detail : 'check did not run'
    return verdict
  }
  if (!selector) {
    verdict.detail = 'no selector'
    return verdict
  }
  const removed = await page.evaluate((sel) => {
    try {
      const nodes = Array.from(document.querySelectorAll(sel))
      nodes.forEach((node) => node.remove())
      return nodes.length
    } catch {
      return -1
    }
  }, selector)
  if (removed <= 0) {
    verdict.detail = `selector matched ${removed} node(s) after a fresh load`
    return verdict
  }
  const result = await runOne(check, 'desktop')
  verdict.verdict = result && result.ok === false ? 'ok' : 'always_passes'
  verdict.detail = result
    ? `${result.detail} (after removing ${removed} node(s))`
    : 'check did not run'
  return verdict
}

try {
  await go(baseUrl)
  await page.waitForTimeout(1000)

  for (const view of views) {
    await evaluateView(view.name, view.width, view.height)
  }

  // Each spec starts on a fresh page: interaction checks (007 starts a walk,
  // which replaces the top search card) must not leak into the next spec.
  // Checks within one spec stay sequential because later checks may read the
  // state an earlier one produced (route summary, live walk controls).
  let currentSpec = null
  for (const check of checks) {
    if (check.spec !== currentSpec) {
      await go(baseUrl)
      currentSpec = check.spec
    }
    await runCheck(check)
  }

  if (plan.selftest) {
    for (const check of checks) {
      selftest.push(await runSelftest(check))
    }
  }
} finally {
  await browser.close()
}

const result = {
  shots: screenshots,
  views: viewFacts,
  checks: checkResults,
  selftest,
  layout: layoutFacts,
}
console.log(JSON.stringify(result))
