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
  if (msg.type() === 'error') consoleErrors.push(msg.text())
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

    const zeroSize = Array.from(
      document.querySelectorAll('button, a, input, [role="button"]'),
    ).filter((el) => el.offsetWidth === 0 || el.offsetHeight === 0).length

    const overflow = document.documentElement.scrollWidth > document.documentElement.clientWidth

    return {
      tiles: tiles.length,
      leaflet: !!leaflet,
      duplicateButtons: dupList,
      zeroSize,
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

async function runCheck(check) {
  const { spec, ac, kind, selector, expect, viewport, value } = check
  const targets = viewport === 'both' ? views.map((v) => v.name) : [viewport]

  for (const viewName of targets) {
    const view = views.find((v) => v.name === viewName)
    if (!view) continue
    await page.setViewportSize({ width: view.width, height: view.height })
    await page.waitForTimeout(200)

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
        case 'route_request': {
          await page.fill(selector, value)
          await page.waitForTimeout(1000)
          ok = routeRequests > 0
          detail = ok ? '/route request fired' : 'no /route request'
          break
        }
      }
    } catch (e) {
      ok = false
      detail = `error: ${e.message}`
    }

    checkResults.push({
      spec,
      ac,
      kind,
      selector,
      viewport: viewName,
      ok,
      detail,
    })
  }
}

try {
  await go(baseUrl)
  await page.waitForTimeout(1000)

  for (const view of views) {
    await evaluateView(view.name, view.width, view.height)
  }

  for (const check of checks) {
    await runCheck(check)
  }
} finally {
  await browser.close()
}

const result = {
  shots: screenshots,
  views: viewFacts,
  checks: checkResults,
  layout: layoutFacts,
}
console.log(JSON.stringify(result))
