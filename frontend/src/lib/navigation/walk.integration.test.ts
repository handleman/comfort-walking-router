import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { get } from 'svelte/store'
import { detectDrift, type DriftSample } from './drift'
import { haversineMeters, type LatLng } from './interpolate'
import { SimulatedProvider } from './simulated'
import { flagOffRoute, onFix, reroute, start, stop, walkMode } from '../walkMode'

/**
 * Integration test for the live-position walk session (spec 007, T9).
 *
 * It drives the *real* walk-mode store (`../walkMode`, shipped by T6-T8) with
 * the real `SimulatedProvider` and the real drift detector: manual ticks move
 * the marker along the route, sustained drift raises the reroute warning, a
 * tapped reroute replaces the route from the current position, arrival within
 * 25 m stops tracking, and Stop ends the session. `fetch` is stubbed for
 * `POST /route` (ADR-005).
 */

/** North-south route: two ~111 m segments, ~222 m in total. */
const ROUTE: LatLng[] = [
  [0, 0],
  [0.001, 0],
  [0.002, 0],
]

/** Last coordinate of the route: the arrival target and the reroute target. */
const DESTINATION: LatLng = ROUTE[ROUTE.length - 1]

/** Meters the simulated walker covers per tick. */
const METERS_PER_TICK = 50

/** A point ~111 m east of the route line: far enough to count as off route. */
const OFF_ROUTE: LatLng = [0, 0.001]

/** A point ~20 m short of the destination: inside the 25 m arrival radius. */
const NEAR_DESTINATION: LatLng = [DESTINATION[0] - 0.00018, DESTINATION[1]]

describe('walk session integration', () => {
  const originalFetch = globalThis.fetch
  let fetchMock: ReturnType<typeof vi.fn>
  let provider: SimulatedProvider | null = null

  beforeEach(() => {
    vi.useFakeTimers()
    fetchMock = vi.fn()
    globalThis.fetch = fetchMock as unknown as typeof fetch
  })

  afterEach(() => {
    provider?.stop()
    provider = null
    globalThis.fetch = originalFetch
    stop()
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  /**
   * Wire an injected `SimulatedProvider` to the walk-mode store: every fix
   * moves the marker, and sustained drift raises the reroute warning.
   */
  function driveSession(route: LatLng[]): SimulatedProvider {
    const sim = new SimulatedProvider(route, METERS_PER_TICK, 0)
    const samples: DriftSample[] = []
    sim.onFix = (fix) => {
      onFix(fix.lat, fix.lng)
      samples.push({ lat: fix.lat, lng: fix.lng, timestamp: fix.timestamp })
      const status = detectDrift(samples, get(walkMode).route ?? route)
      if (status.drifting) {
        flagOffRoute(status.distanceMeters)
      }
    }
    provider = sim
    return sim
  }

  /** Deliver three consecutive off-route fixes spanning 10 s. */
  function feedOffRouteFixes(sim: SimulatedProvider): void {
    sim.onFix({ lat: OFF_ROUTE[0], lng: OFF_ROUTE[1], timestamp: 5_000 })
    sim.onFix({ lat: OFF_ROUTE[0], lng: OFF_ROUTE[1], timestamp: 10_000 })
    sim.onFix({ lat: OFF_ROUTE[0], lng: OFF_ROUTE[1], timestamp: 15_000 })
  }

  /** The current marker position, or a failure when there is none. */
  function markerPos(): LatLng {
    const marker = get(walkMode).markerPos
    if (!marker) throw new Error('expected a marker position')
    return marker
  }

  it('Start places the marker at the route origin', () => {
    start(ROUTE)

    const state = get(walkMode)
    expect(state.active).toBe(true)
    expect(state.markerPos).toEqual(ROUTE[0])
    expect(state.destination).toEqual(DESTINATION)
    expect(state.arrived).toBe(false)
    expect(state.rerouteWarning).toBe(false)
  })

  it('Manual ticks move the marker along the route', () => {
    start(ROUTE)
    const sim = driveSession(ROUTE)

    sim.start() // first fix: the route origin
    expect(haversineMeters(markerPos(), ROUTE[0])).toBeCloseTo(0, 1)

    sim.tick() // second fix: 50 m along the route
    expect(haversineMeters(markerPos(), ROUTE[0])).toBeCloseTo(METERS_PER_TICK, 0)

    sim.tick() // third fix: 100 m along the route
    const marker = markerPos()
    expect(haversineMeters(marker, ROUTE[0])).toBeCloseTo(2 * METERS_PER_TICK, 0)
    expect(marker[1]).toBeCloseTo(0, 6)
  })

  it('Sustained drift shows the reroute warning', () => {
    start(ROUTE)
    const sim = driveSession(ROUTE)
    sim.start()

    expect(get(walkMode).rerouteWarning).toBe(false)

    feedOffRouteFixes(sim)

    const state = get(walkMode)
    expect(state.rerouteWarning).toBe(true)
    expect(state.offRouteMeters).toBeGreaterThan(30)
  })

  it('Tapped reroute replaces the route from the current position', async () => {
    const rerouted: [number, number][] = [
      [0.001, 0.001],
      [0.002, 0.001],
    ]
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ geometry: { type: 'LineString', coordinates: rerouted } }),
    })

    start(ROUTE)
    const sim = driveSession(ROUTE)
    sim.start()
    feedOffRouteFixes(sim)

    const current = markerPos()
    await reroute(current, get(walkMode).destination)

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/route')
    const body = JSON.parse(init.body)
    expect(body.start).toBe(`${current[0]},${current[1]}`)
    expect(body.end).toBe(`${DESTINATION[0]},${DESTINATION[1]}`)

    const state = get(walkMode)
    expect(state.route).toEqual(rerouted)
    expect(state.rerouteWarning).toBe(false)
  })

  it('Arrival within 25 m shows the banner and stops tracking', () => {
    start(ROUTE)
    const sim = driveSession(ROUTE)
    sim.start()

    expect(get(walkMode).arrived).toBe(false)

    sim.onFix({
      lat: NEAR_DESTINATION[0],
      lng: NEAR_DESTINATION[1],
      timestamp: 1_000,
    })

    const state = get(walkMode)
    expect(state.arrived).toBe(true)
    expect(state.active).toBe(false)
  })

  it('Stop ends the session and removes the marker', () => {
    start(ROUTE)
    const sim = driveSession(ROUTE)
    sim.start()
    sim.tick()

    expect(get(walkMode).active).toBe(true)

    stop()

    const state = get(walkMode)
    expect(state.active).toBe(false)
    expect(state.markerPos).toBeNull()
    expect(state.route).toBeNull()
    expect(state.arrived).toBe(false)
  })
})
