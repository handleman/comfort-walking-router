import { afterEach, describe, expect, it, vi } from 'vitest'
import { GpsProvider } from './gps'
import type { LatLng } from './interpolate'
import type { PositionFix } from './positionProvider'

/**
 * Tests for `GpsProvider` (spec 007, T5, AC-2/AC-3). `navigator.geolocation`
 * is stubbed so the watch callbacks can be driven synchronously; the
 * simulated fallback is observed through the same `onFix` stream.
 */

/** Geolocation position error with required properties for type checking. */
interface GeolocationPositionError {
  code: number
  message: string
  PERMISSION_DENIED?: boolean
  POSITION_UNAVAILABLE?: boolean
  TIMEOUT?: boolean
}

/** Watch id the stubbed `watchPosition` hands back. */
const WATCH_ID = 7

/** Short north-south route handed to the provider (and its fallback). */
const ROUTE: readonly LatLng[] = [
  [0, 0],
  [1, 0],
]

/** A fully-formed `GeolocationPosition` with the given coordinates. */
function makePosition(lat: number, lng: number): GeolocationPosition {
  const coords: GeolocationCoordinates = {
    latitude: lat,
    longitude: lng,
    accuracy: 8,
    altitude: null,
    altitudeAccuracy: null,
    heading: null,
    speed: null,
    toJSON: () => ({ latitude: lat, longitude: lng, accuracy: 8 }),
  }
  return {
    coords,
    timestamp: 1234,
    toJSON: () => ({ coords, timestamp: 1234 }),
  }
}

/** Stub `navigator.geolocation` and expose the watch callbacks. */
function stubGeolocation() {
  let onSuccess: PositionCallback = () => {}
  let onError: (err: GeolocationPositionError) => void = () => {}
  const watchPosition = vi.fn(
    (success: PositionCallback, failure: (err: GeolocationPositionError) => void): number => {
      onSuccess = success
      onError = failure
      return WATCH_ID
    },
  )
  const clearWatch = vi.fn()
  vi.stubGlobal('navigator', { geolocation: { watchPosition, clearWatch } })
  return {
    success: (position: GeolocationPosition) => onSuccess(position),
    error: (err: GeolocationPositionError) => onError(err),
    watchPosition,
    clearWatch,
  }
}

/** Collect the fixes a provider emits into an array. */
function collect(provider: GpsProvider): PositionFix[] {
  const fixes: PositionFix[] = []
  provider.onFix = (fix) => fixes.push(fix)
  return fixes
}

describe('GpsProvider', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('emits a successful position fix through onFix', () => {
    const geo = stubGeolocation()
    const provider = new GpsProvider(ROUTE)
    const fixes = collect(provider)

    provider.start()
    expect(geo.watchPosition).toHaveBeenCalledTimes(1)
    expect(fixes).toHaveLength(0) // nothing until the browser reports a fix

    geo.success(makePosition(12.34, -56.78))
    expect(fixes).toEqual([{ lat: 12.34, lng: -56.78, timestamp: 1234, accuracyMeters: 8 }])
    expect(provider.permissionDeniedMessage).toBeNull()
  })

  it('sets permissionDeniedMessage and starts the simulated fallback on denial', () => {
    vi.useFakeTimers()
    const geo = stubGeolocation()
    const provider = new GpsProvider(ROUTE)
    const fixes = collect(provider)

    provider.start()
    geo.error({ code: 1, message: 'User denied geolocation' })

    expect(provider.permissionDeniedMessage).toBe('User denied geolocation')
    // The fallback emits its first fix immediately on start.
    expect(fixes).toHaveLength(1)
    expect(fixes[0]?.lat).toBeCloseTo(0, 6)

    vi.advanceTimersByTime(2000)
    expect(fixes.length).toBeGreaterThan(1)
    expect(geo.clearWatch).not.toHaveBeenCalled()
  })

  it('stop() calls clearWatch with the watch id', () => {
    const geo = stubGeolocation()
    const provider = new GpsProvider(ROUTE)

    provider.start()
    provider.stop()

    expect(geo.clearWatch).toHaveBeenCalledTimes(1)
    expect(geo.clearWatch).toHaveBeenCalledWith(WATCH_ID)
  })

  it('stop() stops the simulated fallback and is idempotent', () => {
    vi.useFakeTimers()
    const geo = stubGeolocation()
    const provider = new GpsProvider(ROUTE)
    const fixes = collect(provider)

    provider.start()
    geo.error({ code: 1, message: 'denied' })
    provider.stop()
    provider.stop() // second call must not throw or re-clear the watch

    const count = fixes.length
    vi.advanceTimersByTime(5000)
    expect(fixes).toHaveLength(count)
    expect(geo.clearWatch).toHaveBeenCalledTimes(1)
  })
})
