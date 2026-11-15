import { describe, expect, it, vi, beforeEach } from 'vitest'
import { get } from 'svelte/store'
import { start, stop, walkMode, rerouteError, reroute } from './walkMode'

function mockRoute(
  coords: [number, number][],
  distanceM: number,
  profile: Array<{ from_m: number; to_m: number; score: number }>,
): void {
  globalThis.fetch = vi.fn(async () => ({
    ok: true,
    json: async () => ({
      geometry: { coordinates: coords },
      distance_m: distanceM,
      comfort_profile: profile,
    }),
  })) as unknown as typeof fetch
}

describe('walkMode reroute comparison (spec 029, AC-2)', () => {
  beforeEach(() => {
    stop()
  })

  it('adopts the candidate on a replace verdict', async () => {
    start([
      [52, 4],
      [52.01, 4.01],
    ])
    const candidate: [number, number][] = [
      [52, 4],
      [52.005, 4.005],
      [52.01, 4.01],
    ]
    mockRoute(candidate, 1200, [{ from_m: 0, to_m: 1200, score: 8 }])
    await reroute([52, 4], [52.01, 4.01])
    expect(get(walkMode).route).toEqual(candidate)
    expect(get(walkMode).rerouteWarning).toBe(false)
  })

  it('asks when the candidate ties the baseline score', async () => {
    start([
      [52, 4],
      [52.01, 4.01],
    ])
    const baseline: [number, number][] = [
      [52, 4],
      [52.01, 4.01],
    ]
    mockRoute(baseline, 1200, [{ from_m: 0, to_m: 1200, score: 8 }])
    await reroute([52, 4], [52.01, 4.01])
    const candidate: [number, number][] = [
      [52, 4],
      [52.005, 4.005],
      [52.01, 4.01],
    ]
    mockRoute(candidate, 1200, [{ from_m: 0, to_m: 1200, score: 8 }])
    await reroute([52, 4], [52.01, 4.01])
    const wm = get(walkMode)
    expect(wm.verdict).toBe('ask')
    expect(wm.delta).toBe(0)
    expect(wm.remainingKm).toBe(1.2)
    expect(wm.rerouteWarning).toBe(true)
    expect(wm.route).toEqual(baseline)
  })

  it('keeps the route with a rerouteError when the candidate is worse', async () => {
    start([
      [52, 4],
      [52.01, 4.01],
    ])
    const baseline: [number, number][] = [
      [52, 4],
      [52.01, 4.01],
    ]
    mockRoute(baseline, 1200, [{ from_m: 0, to_m: 1200, score: 8 }])
    await reroute([52, 4], [52.01, 4.01])
    const candidate: [number, number][] = [
      [52, 4],
      [52.005, 4.005],
      [52.01, 4.01],
    ]
    mockRoute(candidate, 1200, [{ from_m: 0, to_m: 1200, score: 0 }])
    await reroute([52, 4], [52.01, 4.01])
    const wm = get(walkMode)
    expect(wm.verdict).toBe('keep')
    expect(wm.delta).toBe(-8)
    expect(wm.route).toEqual(baseline)
    expect(wm.rerouteWarning).toBe(true)
    const err = get(rerouteError)
    expect(typeof err).toBe('string')
    expect(err!.length).toBeGreaterThan(0)
  })

  it('falls back to adopt without crashing when the comparison fails', async () => {
    start([
      [52, 4],
      [52.01, 4.01],
    ])
    const candidate: [number, number][] = [
      [52.02, 4.02],
      [52.03, 4.03],
    ]
    globalThis.fetch = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        geometry: { coordinates: candidate },
        distance_m: 900,
        comfort_profile: null,
      }),
    })) as unknown as typeof fetch
    await expect(reroute([52, 4], [52.01, 4.01])).resolves.toBeUndefined()
    const wm = get(walkMode)
    expect(wm.route).toEqual(candidate)
    expect(wm.active).toBe(true)
  })
})
