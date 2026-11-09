import { describe, expect, it } from 'vitest'
import {
  detectDrift,
  DRIFT_CONSECUTIVE_THRESHOLD,
  DRIFT_DISTANCE_THRESHOLD_M,
  DRIFT_TIME_THRESHOLD_MS,
  type DriftSample,
} from './drift'
import { type LatLng } from './interpolate'

/**
 * Deterministic tests for `detectDrift` (spec 007, task T3, AC-4): brief
 * drift stays quiet. A single GPS bounce, a run shorter than the time
 * threshold, a run with fewer than the consecutive threshold of fixes, and a
 * fix exactly at the distance threshold must never flag the device drifting.
 */

/** North-south route through the origin; offsets are measured from `[0, 0]`. */
const ROUTE: LatLng[] = [
  [0, 0],
  [1, 0],
]

// Mirrors EARTH_RADIUS_M from the implementation: 1 degree of latitude in meters.
const DEG_LAT_M = (6_371_000 * Math.PI) / 180

/** Latitude `meters` north of the equator, so haversine distance is `meters`. */
const northOf = (meters: number) => meters / DEG_LAT_M

/** Build one fix at `[lat, lng]` with an epoch-ms timestamp. */
function sample(lat: number, lng: number, timestamp: number): DriftSample {
  return { lat, lng, timestamp }
}

/** `count` fixes 100 m off the route, `gapMs` apart, starting at t=0. */
function offRouteRun(count: number, gapMs: number): DriftSample[] {
  return Array.from({ length: count }, (_, i) => sample(northOf(100), 0, i * gapMs))
}

describe('detectDrift — brief drift stays quiet', () => {
  it('is quiet for empty input', () => {
    expect(detectDrift([], ROUTE)).toEqual({
      drifting: false,
      distanceMeters: 0,
      consecutive: 0,
      elapsedMs: 0,
    })
  })

  it('stays quiet for a single fix above the distance threshold', () => {
    const status = detectDrift([sample(northOf(100), 0, 0)], ROUTE)
    expect(status.drifting).toBe(false)
    expect(status.consecutive).toBe(1)
    expect(status.distanceMeters).toBeCloseTo(100, 6)
  })

  it('stays quiet when the run spans less than the time threshold', () => {
    // Three off-route fixes 4 s apart span 8 s < DRIFT_TIME_THRESHOLD_MS.
    const status = detectDrift(offRouteRun(DRIFT_CONSECUTIVE_THRESHOLD, 4_000), ROUTE)
    expect(status.drifting).toBe(false)
    expect(status.consecutive).toBe(DRIFT_CONSECUTIVE_THRESHOLD)
    expect(status.elapsedMs).toBe(8_000)
  })

  it('stays quiet when the run has fewer than the consecutive threshold of fixes', () => {
    // Two off-route fixes 15 s apart span more than DRIFT_TIME_THRESHOLD_MS.
    const status = detectDrift(
      offRouteRun(DRIFT_CONSECUTIVE_THRESHOLD - 1, DRIFT_TIME_THRESHOLD_MS + 5_000),
      ROUTE,
    )
    expect(status.drifting).toBe(false)
    expect(status.consecutive).toBe(DRIFT_CONSECUTIVE_THRESHOLD - 1)
    expect(status.elapsedMs).toBe(DRIFT_TIME_THRESHOLD_MS + 5_000)
  })

  it('flags drift once off-route fixes span the full time threshold', () => {
    // Three off-route fixes 5 s apart span exactly DRIFT_TIME_THRESHOLD_MS,
    // so the time condition is met and the device counts as drifting.
    const status = detectDrift(
      offRouteRun(DRIFT_CONSECUTIVE_THRESHOLD, DRIFT_TIME_THRESHOLD_MS / 2),
      ROUTE,
    )
    expect(status.drifting).toBe(true)
    expect(status.consecutive).toBe(DRIFT_CONSECUTIVE_THRESHOLD)
    expect(status.distanceMeters).toBeCloseTo(100, 6)
    expect(status.elapsedMs).toBe(DRIFT_TIME_THRESHOLD_MS)
  })

  it('stays quiet when off-route fixes span just under the time threshold', () => {
    // Three off-route fixes 4.999 s apart span 9.998 s, just under
    // DRIFT_TIME_THRESHOLD_MS, so drift must not be flagged yet.
    const status = detectDrift(
      offRouteRun(DRIFT_CONSECUTIVE_THRESHOLD, DRIFT_TIME_THRESHOLD_MS / 2 - 1),
      ROUTE,
    )
    expect(status.drifting).toBe(false)
    expect(status.consecutive).toBe(DRIFT_CONSECUTIVE_THRESHOLD)
    expect(status.elapsedMs).toBe(DRIFT_TIME_THRESHOLD_MS - 2)
  })

  it('treats a fix exactly at the distance threshold as on route', () => {
    // The boundary is inclusive: a fix exactly DRIFT_DISTANCE_THRESHOLD_M
    // from the route is not off route, so drift stays quiet.
    const status = detectDrift([sample(northOf(DRIFT_DISTANCE_THRESHOLD_M), 0, 0)], ROUTE)
    expect(status.distanceMeters).toBeCloseTo(DRIFT_DISTANCE_THRESHOLD_M, 6)
    expect(status.drifting).toBe(false)
  })
})

describe('detectDrift — consecutive off-route fixes', () => {
  it('reaches the consecutive threshold after 3 fixes above the distance threshold', () => {
    // Three off-route fixes 5 s apart span exactly DRIFT_TIME_THRESHOLD_MS,
    // so both thresholds are met and the device counts as drifting.
    const status = detectDrift(offRouteRun(DRIFT_CONSECUTIVE_THRESHOLD, 5_000), ROUTE)
    expect(status.consecutive).toBe(DRIFT_CONSECUTIVE_THRESHOLD)
    expect(status.distanceMeters).toBeCloseTo(100, 6)
    expect(status.elapsedMs).toBe(DRIFT_TIME_THRESHOLD_MS)
    expect(status.drifting).toBe(true)
  })

  it('stays quiet after only 2 consecutive off-route fixes', () => {
    // Two off-route fixes 6 s apart span 6 s < DRIFT_TIME_THRESHOLD_MS and
    // fall short of DRIFT_CONSECUTIVE_THRESHOLD, so drift stays quiet.
    const status = detectDrift(offRouteRun(DRIFT_CONSECUTIVE_THRESHOLD - 1, 6_000), ROUTE)
    expect(status.consecutive).toBe(DRIFT_CONSECUTIVE_THRESHOLD - 1)
    expect(status.drifting).toBe(false)
  })

  it('resets the consecutive count after a below-threshold fix', () => {
    // Two off-route fixes, then one fix back on the route: the trailing run
    // is empty, so the counter and clock restart from zero.
    const onRoute = [sample(0, 0, 12_000)]
    const status = detectDrift([...offRouteRun(2, 6_000), ...onRoute], ROUTE)
    expect(status.consecutive).toBe(0)
    expect(status.elapsedMs).toBe(0)
    expect(status.distanceMeters).toBeCloseTo(0, 6)
    expect(status.drifting).toBe(false)
  })
})

describe('detectDrift — threshold boundaries', () => {
  it('flags drift when the off-route run lasts exactly 10 s', () => {
    // Three off-route fixes 5 s apart span exactly 10 s: the time boundary is
    // inclusive, so the device counts as drifting at exactly 10_000 ms.
    const status = detectDrift(offRouteRun(DRIFT_CONSECUTIVE_THRESHOLD, 5_000), ROUTE)
    expect(status.drifting).toBe(true)
    expect(status.elapsedMs).toBe(10_000)
    expect(status.consecutive).toBe(DRIFT_CONSECUTIVE_THRESHOLD)
  })

  it("reports 'both' when the time and consecutive conditions hold together", () => {
    // The same run both spans the 10 s time threshold and reaches the
    // consecutive-fix threshold, so the drift reason is 'both'.
    const status = detectDrift(offRouteRun(DRIFT_CONSECUTIVE_THRESHOLD, 5_000), ROUTE)
    expect(status.drifting).toBe(true)
    expect(status.reason).toBe('both')
  })
})
