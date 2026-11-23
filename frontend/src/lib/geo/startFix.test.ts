// Tests for `requestStartFix` (spec 040, T18 / AC-5): the geolocation-on-start
// helper must resolve to a fix (coords + reverse-geocoded label) or a no-fix
// outcome, and never throw. `navigator.geolocation` is stubbed per test.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { requestStartFix } from './startFix'

/** Stub `navigator.geolocation` and capture the getCurrentPosition callbacks. */
function stubGeo() {
  let success: (p: GeolocationPosition) => void = () => {}
  let failure: (e: GeolocationPositionError) => void = () => {}
  const getCurrentPosition = vi.fn(
    (ok: (p: GeolocationPosition) => void, err: (e: GeolocationPositionError) => void) => {
      success = ok
      failure = err
    },
  )
  vi.stubGlobal('navigator', { geolocation: { getCurrentPosition } })
  return {
    getCurrentPosition,
    fix: (lat: number, lng: number) =>
      success({ coords: { latitude: lat, longitude: lng } } as GeolocationPosition),
    error: (code: number) =>
      failure({
        code,
        PERMISSION_DENIED: 1,
        POSITION_UNAVAILABLE: 2,
        TIMEOUT: 3,
      } as GeolocationPositionError),
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.doUnmock('../map/picker')
  vi.resetModules()
})

describe('requestStartFix', () => {
  it('resolves no-fix when geolocation is unsupported', async () => {
    await expect(requestStartFix(undefined)).resolves.toEqual({
      kind: 'no-fix',
      reason: 'Geolocation unsupported',
    })
  })

  it('resolves a fix with reverse-geocoded label on success', async () => {
    const geo = stubGeo()
    vi.doMock('../map/picker', () => ({ reverseLabel: async () => 'Marienplatz, München' }))
    const { requestStartFix: fresh } = await import('./startFix')
    const p = fresh()
    geo.fix(48.1375, 11.575)
    await expect(p).resolves.toEqual({
      kind: 'fix',
      coords: [48.1375, 11.575],
      label: 'Marienplatz, München',
    })
    expect(geo.getCurrentPosition).toHaveBeenCalled()
  })

  it('resolves no-fix with reason on permission denied', async () => {
    const geo = stubGeo()
    const p = requestStartFix()
    geo.error(1)
    await expect(p).resolves.toEqual({ kind: 'no-fix', reason: 'Permission denied' })
  })

  it('resolves no-fix with reason on timeout', async () => {
    const geo = stubGeo()
    const p = requestStartFix()
    geo.error(3)
    await expect(p).resolves.toEqual({ kind: 'no-fix', reason: 'Timed out' })
  })
})
