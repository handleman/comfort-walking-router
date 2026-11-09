import { describe, expect, it } from 'vitest'
import { ARRIVAL_RADIUS_M, checkArrival, type ArrivalSample } from './arrival'

/**
 * Deterministic tests for `checkArrival` (spec 007, T4, AC-1/AC-7).
 * Everything is pure: positions and times come from the samples themselves,
 * never from a clock, so every case below is fully reproducible.
 */

// Mirrors EARTH_RADIUS_M from the implementation: 1 degree of latitude in meters.
const DEG_LAT_M = (6_371_000 * Math.PI) / 180

/** Arrival target: one full degree of latitude north of the equator. */
const DESTINATION: [number, number] = [1, 0]

/** Build a sample at `lat` with a fixed accuracy and timestamp. */
function sample(lat: number, lng = 0): ArrivalSample {
  return { position: [lat, lng], accuracyMeters: 5, timestampMs: 1_000 }
}

describe('checkArrival', () => {
  it('is not arrived when far from the destination', () => {
    // One degree of latitude away is ~111 km, far beyond ARRIVAL_RADIUS_M.
    const status = checkArrival(sample(0), DESTINATION)
    expect(status.arrived).toBe(false)
    expect(status.distanceMeters).toBeCloseTo(DEG_LAT_M, 0)
  })

  it('is arrived exactly at the 25 m boundary (inclusive <=)', () => {
    // Due south of the destination by exactly ARRIVAL_RADIUS_M meters; along a
    // meridian haversine is exact, so this lands on the boundary itself.
    const boundaryLat = DESTINATION[0] - ARRIVAL_RADIUS_M / DEG_LAT_M
    const status = checkArrival(sample(boundaryLat), DESTINATION)
    expect(status.arrived).toBe(true)
    expect(status.distanceMeters).toBeCloseTo(ARRIVAL_RADIUS_M, 6)
  })

  it('is arrived inside the radius (well within 25 m)', () => {
    // 20 m south of the destination: strictly inside ARRIVAL_RADIUS_M.
    const insideLat = DESTINATION[0] - 20 / DEG_LAT_M
    const status = checkArrival(sample(insideLat), DESTINATION)
    expect(status.arrived).toBe(true)
    expect(status.distanceMeters).toBeCloseTo(20, 6)
  })

  it('is idempotent: repeated calls within the radius stay arrived', () => {
    // AC-7: checkArrival is a pure function of the sample, so calling it
    // repeatedly on the same in-radius fix must keep returning arrived: true.
    const insideLat = DESTINATION[0] - 20 / DEG_LAT_M
    const first = checkArrival(sample(insideLat), DESTINATION)
    const second = checkArrival(sample(insideLat), DESTINATION)
    const third = checkArrival(sample(insideLat), DESTINATION)
    expect(first.arrived).toBe(true)
    expect(second.arrived).toBe(true)
    expect(third.arrived).toBe(true)
    expect(second).toEqual(first)
    expect(third).toEqual(first)
  })
})
