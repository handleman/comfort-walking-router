import { afterEach, describe, expect, it, vi } from 'vitest'
import { SimulatedProvider } from './simulated'
import type { PositionFix } from './positionProvider'

/**
 * Deterministic tests for `SimulatedProvider` (spec 007, T5, AC-2/AC-3).
 * Movement is driven by synchronous `tick()` calls and the seed only shapes
 * the reported accuracy, so every case below is fully deterministic: no clock,
 * no GPS, no randomness.
 */

// Mirrors EARTH_RADIUS_M from interpolate.ts: 1 degree of latitude in meters.
const DEG_LAT_M = (6_371_000 * Math.PI) / 180

/** North-south line: each step is exactly one degree of latitude apart. */
const ROUTE = [
  [0, 0],
  [1, 0],
  [2, 0],
] as const

/** Collect the fixes a provider emits into an array. */
function collect(provider: SimulatedProvider): PositionFix[] {
  const fixes: PositionFix[] = []
  provider.onFix = (fix) => fixes.push(fix)
  return fixes
}

describe('SimulatedProvider', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('produces an identical fix sequence for identical seeds', () => {
    const a = new SimulatedProvider(ROUTE, DEG_LAT_M, 42)
    const b = new SimulatedProvider(ROUTE, DEG_LAT_M, 42)
    const fixesA = collect(a)
    const fixesB = collect(b)

    a.start()
    b.start()
    a.tick()
    a.tick()
    b.tick()
    b.tick()
    a.stop()
    b.stop()

    expect(fixesA.length).toBeGreaterThan(0)
    expect(fixesA).toEqual(fixesB)
  })

  it('starts at a different fix for different seeds', () => {
    // The seed shapes accuracyMeters deterministically (5 + |seed| % 10), so
    // seeds 0 and 3 differ from the very first emitted fix.
    const a = new SimulatedProvider(ROUTE, DEG_LAT_M, 0)
    const b = new SimulatedProvider(ROUTE, DEG_LAT_M, 3)
    const fixesA = collect(a)
    const fixesB = collect(b)

    a.start()
    b.start()
    a.stop()
    b.stop()

    expect(fixesA).toHaveLength(1)
    expect(fixesB).toHaveLength(1)
    expect(fixesA[0]).not.toEqual(fixesB[0])
    expect(fixesA[0]?.accuracyMeters).not.toBe(fixesB[0]?.accuracyMeters)
  })

  it('emits exactly one fix per tick() call', () => {
    const provider = new SimulatedProvider(ROUTE, DEG_LAT_M, 0)
    const fixes = collect(provider)

    provider.tick()
    expect(fixes).toHaveLength(1)
    expect(fixes[0]?.timestamp).toBe(0)

    provider.tick()
    expect(fixes).toHaveLength(2)
    expect(fixes[1]?.timestamp).toBe(1000)

    // One degree of latitude per tick along the north-south route.
    expect(fixes[1]?.lat).toBeCloseTo(1, 6)
    expect(fixes[1]?.lng).toBeCloseTo(0, 6)
  })

  it('emits no further fixes after stop()', () => {
    vi.useFakeTimers()
    const provider = new SimulatedProvider(ROUTE, DEG_LAT_M, 0)
    const fixes = collect(provider)

    provider.start()
    expect(fixes).toHaveLength(1) // first fix is immediate

    vi.advanceTimersByTime(2000)
    expect(fixes).toHaveLength(3)

    provider.stop()
    vi.advanceTimersByTime(5000)
    expect(fixes).toHaveLength(3) // interval cleared: nothing new
  })

  it('is safe to call stop() more than once', () => {
    vi.useFakeTimers()
    const provider = new SimulatedProvider(ROUTE, DEG_LAT_M, 0)
    const fixes = collect(provider)

    provider.start()
    provider.stop()
    provider.stop()
    vi.advanceTimersByTime(3000)

    expect(fixes).toHaveLength(1)
  })
})
