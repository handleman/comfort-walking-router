/**
 * Simulated `PositionProvider` for the live position walk (spec 007, T5).
 *
 * Walks a route (LineString as `[lat, lng]` pairs) at a fixed
 * `distanceMetersPerTick`, emitting one fix per tick. The first fix is emitted
 * immediately on `start()`; subsequent fixes arrive every second via
 * `setInterval`. `tick()` advances exactly one fix synchronously so tests and
 * the demo stay deterministic (AC-2, AC-3) — no clock reads, no randomness.
 */

import { interpolateAlongLineString, type LatLng } from './interpolate'
import type { OnFix, PositionFix, PositionProvider } from './positionProvider'

/** Real-time cadence of simulated fixes. */
const TICK_INTERVAL_MS = 1000

/**
 * Simulated GPS source that walks a route deterministically.
 *
 * Fix `n` is the point reached after `n` ticks of `distanceMetersPerTick`
 * along the route (clamped to the route end), timestamped `n * 1s` — the
 * timestamp comes from the tick count, never a clock read.
 */
export class SimulatedProvider implements PositionProvider {
  /** Callback that receives each simulated fix. */
  onFix: OnFix = () => {}

  private readonly route: readonly LatLng[]
  private readonly distanceMetersPerTick: number
  private readonly accuracyMeters: number
  private tickCount = 0
  private intervalId: ReturnType<typeof setInterval> | null = null

  constructor(route: readonly LatLng[], distanceMetersPerTick = 10, seed = 0) {
    this.route = route
    this.distanceMetersPerTick = distanceMetersPerTick
    // Seed only shapes the reported accuracy, deterministically: same seed,
    // same fix stream. Movement itself never depends on it.
    this.accuracyMeters = 5 + (Math.abs(seed) % 10)
  }

  /** Emit the first fix immediately, then one fix per second. */
  start(): void {
    this.emitFix()
    if (this.intervalId !== null) return
    this.intervalId = setInterval(() => this.tick(), TICK_INTERVAL_MS)
  }

  /** Clear the interval; safe to call more than once. */
  stop(): void {
    if (this.intervalId !== null) {
      clearInterval(this.intervalId)
      this.intervalId = null
    }
  }

  /** Advance exactly one fix synchronously (deterministic; for tests/demo). */
  tick(): void {
    this.emitFix()
  }

  private emitFix(): void {
    const point = interpolateAlongLineString(
      this.route,
      this.distanceMetersPerTick,
      () => this.tickCount,
    )
    if (!point) return
    const fix: PositionFix = {
      lat: point[0],
      lng: point[1],
      timestamp: this.tickCount * TICK_INTERVAL_MS,
      accuracyMeters: this.accuracyMeters,
    }
    this.tickCount += 1
    this.onFix(fix)
  }
}
