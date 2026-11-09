/**
 * Real GPS `PositionProvider` for the live position walk (spec 007, T5).
 *
 * Wraps `navigator.geolocation.watchPosition` and emits one fix per callback,
 * taking `lat`/`lng` from `coords.latitude`/`coords.longitude`. When permission
 * is denied, or the Geolocation API is unavailable entirely, it falls back to a
 * `SimulatedProvider` walking the same route, so the walk always has a fix
 * stream (AC-2, AC-3). The browser's denial message is kept in
 * `permissionDeniedMessage` so the UI can explain why the walk is simulated.
 */

import type { LatLng } from './interpolate'
import type { OnFix, PositionFix, PositionProvider } from './positionProvider'
import { SimulatedProvider } from './simulated'

/** `GeolocationPositionError.code` value for a denied permission request. */
const PERMISSION_DENIED = 1

/**
 * GPS-backed position source with a deterministic simulated fallback.
 *
 * `start()` begins watching the real position; if permission is denied or
 * geolocation is missing, a `SimulatedProvider` over the same route takes
 * over. `stop()` clears the watch and stops the fallback; safe to call twice.
 */
export class GpsProvider implements PositionProvider {
  /** Callback that receives each fix (real or simulated). */
  onFix: OnFix = () => {}

  /** Browser's denial message once permission is refused; null before that. */
  permissionDeniedMessage: string | null = null

  private readonly route: readonly LatLng[]
  private readonly distanceMetersPerTick: number
  private watchId: number | null = null
  private sim: SimulatedProvider | null = null

  constructor(route: readonly LatLng[], distanceMetersPerTick = 10) {
    this.route = route
    this.distanceMetersPerTick = distanceMetersPerTick
  }

  /** Watch the real position, or fall back to the simulated walk. */
  start(): void {
    if (this.watchId !== null || this.sim !== null) return
    if (typeof navigator === 'undefined' || !navigator.geolocation) {
      // No Geolocation API (unsupported browser or non-secure context).
      this.startFallback()
      return
    }
    this.watchId = navigator.geolocation.watchPosition(
      (position) => this.emitFix(position),
      (error) => {
        if (error.code !== PERMISSION_DENIED) return
        this.permissionDeniedMessage = error.message
        this.startFallback()
      },
    )
  }

  /** Clear the watch and stop the simulated fallback; idempotent. */
  stop(): void {
    if (this.watchId !== null) {
      navigator.geolocation.clearWatch(this.watchId)
      this.watchId = null
    }
    if (this.sim !== null) {
      this.sim.stop()
      this.sim = null
    }
  }

  private emitFix(position: GeolocationPosition): void {
    const fix: PositionFix = {
      lat: position.coords.latitude,
      lng: position.coords.longitude,
      timestamp: position.timestamp,
      accuracyMeters: position.coords.accuracy,
    }
    this.onFix(fix)
  }

  private startFallback(): void {
    if (this.sim !== null) return
    this.sim = new SimulatedProvider(this.route, this.distanceMetersPerTick)
    this.sim.onFix = this.onFix
    this.sim.start()
  }
}
