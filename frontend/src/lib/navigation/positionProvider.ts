/**
 * Position provider contract for the live position walk (spec 007, T5).
 *
 * The walk needs a stream of position fixes, but it must not care where they
 * come from (browser geolocation, a replayed trace, a test harness). This file
 * defines the minimal interface the walk consumes; concrete sources implement
 * `PositionProvider` and push fixes through the `onFix` callback.
 */

/** One observed position fix delivered by a `PositionProvider`. */
export interface PositionFix {
  /** Observed latitude in decimal degrees. */
  lat: number
  /** Observed longitude in decimal degrees. */
  lng: number
  /** Fix time in milliseconds (taken from the fix, never a clock read). */
  timestamp: number
  /** GPS accuracy radius in meters, when the source reports one. */
  accuracyMeters?: number
}

/** Callback invoked for each fix produced by a `PositionProvider`. */
export type OnFix = (fix: PositionFix) => void

/** Minimal source of position fixes consumed by the live position walk. */
export interface PositionProvider {
  /** Register the callback that receives each fix. */
  onFix: OnFix
  /** Begin producing fixes. */
  start(): void
  /** Stop producing fixes and release the underlying source. */
  stop(): void
}
