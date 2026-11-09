import { describe, expect, it } from 'vitest'
import { haversineMeters } from './interpolate'
import { snapToRoute } from './snap'

/**
 * Deterministic tests for `snapToRoute` edge cases (spec 007, T2, AC-4).
 * Pure spherical math only: no clock, no GPS, no randomness.
 */

describe('snapToRoute', () => {
  it('returns null for an empty line', () => {
    expect(snapToRoute([10, 20], [])).toBeNull()
  })

  it('snaps a single-point line to that point with the haversine off-route distance', () => {
    const fix: [number, number] = [1, 1]
    const point: [number, number] = [2, 3]
    const result = snapToRoute(fix, [point])
    expect(result).not.toBeNull()
    expect(result?.snapped).toEqual(point)
    expect(result?.segmentIndex).toBe(0)
    expect(result?.distanceOffRoute).toBeCloseTo(haversineMeters(fix, point), 6)
  })

  it('returns the fix itself with ~0 off-route distance when it lies exactly on a segment', () => {
    const line: [number, number][] = [
      [0, 0],
      [0, 1],
    ]
    const fix: [number, number] = [0, 0.5]
    const result = snapToRoute(fix, line)
    expect(result).not.toBeNull()
    expect(result?.snapped[0]).toBeCloseTo(fix[0], 6)
    expect(result?.snapped[1]).toBeCloseTo(fix[1], 6)
    expect(result?.segmentIndex).toBe(0)
    expect(result?.distanceOffRoute).toBeCloseTo(0, 6)
  })

  it('projects a fix offset perpendicular to a segment and reports the offset as distanceOffRoute', () => {
    const line: [number, number][] = [
      [0, 0],
      [0, 1],
    ]
    const fix: [number, number] = [0.001, 0.5]
    const projection: [number, number] = [0, 0.5]
    const result = snapToRoute(fix, line)
    expect(result).not.toBeNull()
    expect(result?.snapped[0]).toBeCloseTo(projection[0], 6)
    expect(result?.snapped[1]).toBeCloseTo(projection[1], 6)
    expect(result?.segmentIndex).toBe(0)
    expect(result?.distanceOffRoute).toBeCloseTo(haversineMeters(fix, projection), 6)
  })

  it('clamps a fix beyond the segment start to the segment start', () => {
    const line: [number, number][] = [
      [0, 0],
      [0, 1],
    ]
    const fix: [number, number] = [-0.001, 0]
    const result = snapToRoute(fix, line)
    expect(result).not.toBeNull()
    expect(result?.snapped[0]).toBeCloseTo(line[0][0], 6)
    expect(result?.snapped[1]).toBeCloseTo(line[0][1], 6)
    expect(result?.segmentIndex).toBe(0)
    expect(result?.distanceOffRoute).toBeCloseTo(haversineMeters(fix, line[0]), 6)
  })

  it('clamps a fix beyond the segment end to the segment end', () => {
    const line: [number, number][] = [
      [0, 0],
      [0, 1],
    ]
    const fix: [number, number] = [0.001, 1]
    const result = snapToRoute(fix, line)
    expect(result).not.toBeNull()
    expect(result?.snapped[0]).toBeCloseTo(line[1][0], 6)
    expect(result?.snapped[1]).toBeCloseTo(line[1][1], 6)
    expect(result?.segmentIndex).toBe(0)
    expect(result?.distanceOffRoute).toBeCloseTo(haversineMeters(fix, line[1]), 6)
  })

  it('picks the nearest segment of a multi-segment route', () => {
    const line: [number, number][] = [
      [0, 0],
      [0, 1],
      [0, 2],
    ]
    const fix: [number, number] = [0.001, 1.5]
    const projection: [number, number] = [0, 1.5]
    const result = snapToRoute(fix, line)
    expect(result).not.toBeNull()
    expect(result?.segmentIndex).toBe(1)
    expect(result?.snapped[0]).toBeCloseTo(projection[0], 6)
    expect(result?.snapped[1]).toBeCloseTo(projection[1], 6)
    expect(result?.distanceOffRoute).toBeCloseTo(haversineMeters(fix, projection), 6)
  })

  it('reports distanceOffRoute equal to the haversine distance between fix and snapped point', () => {
    const line: [number, number][] = [
      [10, 0],
      [10, 1],
    ]
    const fix: [number, number] = [10.002, 0.3]
    const result = snapToRoute(fix, line)
    if (!result) throw new Error('expected snapToRoute to return a result')
    expect(result.distanceOffRoute).toBeCloseTo(haversineMeters(fix, result.snapped), 6)
  })

  it('is deterministic: repeated calls with identical input return identical results', () => {
    const line: [number, number][] = [
      [0, 0],
      [0, 1],
      [0, 2],
    ]
    const fix: [number, number] = [0.001, 1.5]
    const first = snapToRoute(fix, line)
    const second = snapToRoute(fix, line)
    expect(first).not.toBeNull()
    expect(second).not.toBeNull()
    expect(second).toEqual(first)
  })
})
