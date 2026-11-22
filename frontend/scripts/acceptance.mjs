#!/usr/bin/env node
/** Spec acceptance browser runner (043).

One Node process driven by a JSON plan (`plan.json`):
* launch Chromium with geolocation granted and `__ROUTE_FIXTURES__=1`
* resize to desktop + mobile viewports, screenshot
* run deterministic checks per spec/AC
* emit one JSON document with shots, views (global facts), checks (per-AC results)

This is the only Playwright dependency in the harness; Python stays model-only.
*/

import { chromium, devices } from 'playwright';
import { mkdirSync, writeFileSync, readFileSync } from 'fs';
import { resolve } from 'path';

const PLAN_FILE = process.argv[2];
if (!PLAN_FILE) {
  console.error('usage: acceptance.mjs <plan.json>');
  process.exit(1);
}

const plan = JSON.parse(readFileSync(PLAN_FILE, 'utf-8'));
const baseUrl = plan.baseUrl;
const outDir = plan.outDir;
const views = plan.views || [];
const checks = plan.checks || [];

mkdirSync(outDir, { recursive: true });

const screenshots = {};
const viewFacts = {};
const checkResults = [];

const browser = await chromium.launch({
  headless: true,
  args: ['--no-sandbox', '--disable-setuid-sandbox'],
});

const context = await browser.newContext({
  geolocation: { latitude: 48.137, longitude: 11.575, accuracy: 10 },
  permissions: ['geolocation'],
  viewport: { width: 1280, height: 800 },
});

await context.addInitScript(() => {
  (window as { __ROUTE_FIXTURES__?: number }).__ROUTE_FIXTURES__ = 1;
});

const page = await context.newPage();

const consoleErrors: string[] = [];
page.on('console', msg => {
  if (msg.type() === 'error') consoleErrors.push(msg.text());
});

page.on('pageerror', err => {
  consoleErrors.push(err.message);
});

let routeRequests = 0;
page.on('request', req => {
  if (req.url().includes('/route')) routeRequests++;
});

async function go(url: string) {
  await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(500);
}

async function evaluateView(name: string, width: number, height: number) {
  await page.setViewportSize({ width, height });
  await page.waitForTimeout(300);

  const shotPath = resolve(outDir, `${name}.png`);
  await page.screenshot({ path: shotPath, fullPage: true });
  screenshots[name] = shotPath;

  const facts = await page.evaluate(() => {
    const tiles = document.querySelectorAll('.leaflet-tile');
    const leaflet = document.querySelector('.leaflet-container');
    const buttons = Array.from(document.querySelectorAll('button, [role="button"]'))
      .filter(el => el.offsetParent !== null)
      .map(el => ({
        text: (el.textContent || '').trim().slice(0, 80),
        tag: el.tagName.toLowerCase(),
        class: el.className,
        visible: el.offsetWidth > 0 && el.offsetHeight > 0,
      }));
    const duplicates = buttons
      .filter(b => b.visible)
      .reduce((acc, b) => {
        const key = b.text || b.class || b.tag;
        acc[key] = (acc[key] || 0) + 1;
        return acc;
      }, {});
    const dupList = Object.entries(duplicates)
      .filter(([, c]) => c > 1)
      .map(([text]) => text);

    const zeroSize = Array.from(document.querySelectorAll('button, a, input, [role="button"]'))
      .filter(el => el.offsetWidth === 0 || el.offsetHeight === 0).length;

    const overflow = document.documentElement.scrollWidth > document.documentElement.clientWidth;

    return {
      tiles: tiles.length,
      leaflet: !!leaflet,
      duplicateButtons: dupList,
      zeroSize,
      overflow,
      routeRequests: 0,
    };
  });

  facts.routeRequests = routeRequests;
  routeRequests = 0;
  viewFacts[name] = facts;
}

async function runCheck(check) {
  const { spec, ac, kind, selector, expect, viewport, value } = check;
  const targets = viewport === 'both' ? views.map(v => v.name) : [viewport];

  for (const viewName of targets) {
    const view = views.find(v => v.name === viewName);
    if (!view) continue;
    await page.setViewportSize({ width: view.width, height: view.height });
    await page.waitForTimeout(200);

    let ok = false;
    let detail = '';

    try {
      switch (kind) {
        case 'exists': {
          const count = await page.locator(selector).count();
          ok = count > 0;
          detail = ok ? `found ${count} element(s)` : 'not found';
          break;
        }
        case 'absent': {
          const count = await page.locator(selector).count();
          ok = count === 0;
          detail = ok ? 'absent' : `found ${count} element(s)`;
          break;
        }
        case 'count': {
          const count = await page.locator(selector).count();
          ok = count === Number(expect);
          detail = `count ${count} vs expect ${expect}`;
          break;
        }
        case 'min_count': {
          const count = await page.locator(selector).count();
          ok = count >= Number(expect);
          detail = `count ${count} >= ${expect}`;
          break;
        }
        case 'text': {
          const text = await page.locator(selector).textContent() || '';
          ok = String(text).includes(String(expect));
          detail = ok ? `text matches` : `text "${text.slice(0, 100)}" missing "${expect}"`;
          break;
        }
        case 'value_set': {
          const val = await page.locator(selector).inputValue();
          ok = val === String(value);
          detail = ok ? `value set` : `value "${val}" != "${value}"`;
          break;
        }
        case 'route_request': {
          await page.fill(selector, value);
          await page.waitForTimeout(1000);
          ok = routeRequests > 0;
          detail = ok ? '/route request fired' : 'no /route request';
          break;
        }
      }
    } catch (e) {
      ok = false;
      detail = `error: ${e.message}`;
    }

    checkResults.push({
      spec,
      ac,
      kind,
      selector,
      viewport: viewName,
      ok,
      detail,
    });
  }
}

try {
  await go(baseUrl);
  await page.waitForTimeout(1000);

  for (const view of views) {
    await evaluateView(view.name, view.width, view.height);
  }

  for (const check of checks) {
    await runCheck(check);
  }
} finally {
  await browser.close();
}

const result = {
  shots: screenshots,
  views: viewFacts,
  checks: checkResults,
};
console.log(JSON.stringify(result));