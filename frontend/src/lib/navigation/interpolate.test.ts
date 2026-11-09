import { describe, expect, it } from 'vitest'
import { haversineMeters, interpolateAlongLineString } from './interpolate'

/**
 * Deterministic tests for `interpolateAlongLineString` (spec 007, T1, AC-2/AC-8).
 * The tick source is injected, so every case below is fully deterministic:
 * no clock, no GPS, no randomness.
 */

// Mirrors EARTH_RADIUS_M from the implementation: 1 degree of latitude in meters.
const DEG_LAT_M = (6_371_000 * Math.PI) / 180

/** North-south line: each step is exactly one degree of latitude apart. */
const TWO_DEG_LINE = [
  [0, 0],
  [1, 0],
  [2, 0],
] as const

describe('interpolateAlongLineString', () => {
  it('returns null for an empty line', () => {
    expect(interpolateAlongLineString([], 100, () => 1)).toBeNull()
  })

  it('returns the single point for a one-coordinate line', () => {
    expect(interpolateAlongLineString([[5, 6]], 100, () => 7)).toEqual([5, 6])
  })

  it('stays at the first coordinate for zero ticks', () => {
    expect(interpolateAlongLineString(TWO_DEG_LINE, DEG_LAT_M, () => 0)).toEqual([0, 0])
  })

  it('clamps a negative per-tick distance to the first coordinate', () => {
    expect(interpolateAlongLineString(TWO_DEG_LINE, -50, () => 3)).toEqual([0, 0])
  })

  it('advances one full degree with ticks() === 1', () => {
    const point = interpolateAlongLineString(TWO_DEG_LINE, DEG_LAT_M, () => 1)
    expect(point).not.toBeNull()
    expect(point?.[0]).toBeCloseTo(1, 6)
    expect(point?.[1]).toBeCloseTo(0, 6)
  })

  it('multiplies per-tick distance by the injected tick count', () => {
    // Half a degree per tick, two ticks => one degree north.
    const point = interpolateAlongLineString(TWO_DEG_LINE, DEG_LAT_M / 2, () => 2)
    expect(point).not.toBeNull()
    expect(point?.[0]).toBeCloseTo(1, 6)
    expect(point?.[1]).toBeCloseTo(0, 6)
  })

  it('interpolates mid-segment between coordinates', () => {
    // 1.5 degrees along the line lands halfway through the second segment.
    const point = interpolateAlongLineString(TWO_DEG_LINE, DEG_LAT_M * 1.5, () => 1)
    expect(point).not.toBeNull()
    expect(point?.[0]).toBeCloseTo(1.5, 6)
    expect(point?.[1]).toBeCloseTo(0, 6)
  })

  it('clamps a target past the end of the line to the last coordinate', () => {
    const point = interpolateAlongLineString(TWO_DEG_LINE, DEG_LAT_M, () => 10)
    expect(point).not.toBeNull()
    expect(point?.[0]).toBeCloseTo(2, 6)
    expect(point?.[1]).toBeCloseTo(0, 6)
  })

  it('uses the injected tick source exactly once per call', () => {
    let calls = 0
    const ticks = () => {
      calls += 1
      return 1
    }
    interpolateAlongLineString(TWO_DEG_LINE, DEG_LAT_M, ticks)
    expect(calls).toBe(1)
  })

  it('is deterministic: identical ticks always yield identical points', () => {
    const a = interpolateAlongLineString(TWO_DEG_LINE, DEG_LAT_M / 4, () => 3)
    const b = interpolateAlongLineString(TWO_DEG_LINE, DEG_LAT_M / 4, () => 3)
    expect(a).toEqual(b)
  })

  it('walks monotonically north as the injected tick count grows', () => {
    const walk = [0, 1, 2, 3, 4].map((n) =>
      interpolateAlongLineString(TWO_DEG_LINE, DEG_LAT_M / 2, () => n),
    )
    expect(walk[0]).toEqual([0, 0])
    expect(walk[1]?.[0]).toBeCloseTo(0.5, 6)
    expect(walk[2]?.[0]).toBeCloseTo(1, 6)
    expect(walk[3]?.[0]).toBeCloseTo(1.5, 6)
    expect(walk[4]?.[0]).toBeCloseTo(2, 6) // clamped at the last coordinate
  })

  it('skips zero-length duplicate segments without dividing by zero', () => {
    const line = [
      [0, 0],
      [0, 0],
      [1, 0],
    ] as const
    const point = interpolateAlongLineString(line, DEG_LAT_M, () => 1)
    expect(point?.[0]).toBeCloseTo(1, 6)
    expect(point?.[1]).toBeCloseTo(0, 6)
  })

  it('returns a fresh coordinate array, not a reference into the line', () => {
    const line = [[5, 6]] as const
    const point = interpolateAlongLineString(line, 100, () => 1)
    expect(point).not.toBe(line[0])
  })
})

describe('haversineMeters', () => {
  it('measures one degree of latitude as ~111.195 km', () => {
    expect(haversineMeters([0, 0], [1, 0])).toBeCloseTo(DEG_LAT_M, 3)
  })

  it('is zero for identical points', () => {
    expect(haversineMeters([12.34, 56.78], [12.34, 56.78])).toBe(0)
  })
})
