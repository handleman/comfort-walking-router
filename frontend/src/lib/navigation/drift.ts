/**
 * Drift detection for the live-navigation view (spec 007, task T3, AC-4).
 *
 * A fix counts as "off route" when it sits more than
 * `DRIFT_DISTANCE_THRESHOLD_M` from every route vertex. The device is only
 * reported as drifting once `DRIFT_CONSECUTIVE_THRESHOLD` consecutive fixes
 * are off route AND those fixes span at least `DRIFT_TIME_THRESHOLD_MS`, so a
 * single GPS bounce never triggers a reroute. Pure and deterministic so tests
 * can assert exact values (AC-4).
 */

import { haversineMeters, type LatLng } from './interpolate'

/** Meters from the route beyond which a single fix is considered off route. */
export const DRIFT_DISTANCE_THRESHOLD_M = 30

/** Milliseconds the run of off-route fixes must span before flagging drift. */
export const DRIFT_TIME_THRESHOLD_MS = 10_000

/** Consecutive off-route fixes required before the device counts as drifting. */
export const DRIFT_CONSECUTIVE_THRESHOLD = 3

/** One GPS fix observed while navigating. */
export interface DriftSample {
  /** Latitude in degrees. */
  lat: number
  /** Longitude in degrees. */
  lng: number
  /** Fix time as epoch milliseconds. */
  timestamp: number
}

/** Which drift threshold condition(s) the current off-route run satisfies. */
export type DriftReason = 'time' | 'consecutive' | 'both'

/** Result of evaluating the fix history against the route. */
export interface DriftStatus {
  /** True once the consecutive and time thresholds are both met. */
  drifting: boolean
  /** Which threshold condition(s) hold; undefined when neither does. */
  reason?: DriftReason
  /** Distance in meters from the newest fix to the nearest route vertex. */
  distanceMeters: number
  /** Length of the current trailing run of consecutive off-route fixes. */
  consecutive: number
  /** Milliseconds spanned by that run (0 when the run is empty). */
  elapsedMs: number
}

/** Smallest distance in meters from `point` to any vertex of `route`. */
export function distanceToRouteMeters(point: LatLng, route: LatLng[]): number {
  let best = Infinity
  for (const vertex of route) {
    const d = haversineMeters(point, vertex)
    if (d < best) best = d
  }
  return best
}

/**
 * Evaluate the fix history against the route. Samples are processed in the
 * order given (oldest first); only the trailing run of consecutive off-route
 * fixes counts, so a single on-route fix resets the counter and the clock.
 * Returns the resulting `DriftStatus` without mutating either argument.
 */
export function detectDrift(samples: DriftSample[], route: LatLng[]): DriftStatus {
  let consecutive = 0
  let runStart = 0
  let distanceMeters = 0

  for (const sample of samples) {
    const point: LatLng = [sample.lat, sample.lng]
    distanceMeters = distanceToRouteMeters(point, route)
    if (distanceMeters > DRIFT_DISTANCE_THRESHOLD_M) {
      if (consecutive === 0) runStart = sample.timestamp
      consecutive += 1
    } else {
      consecutive = 0
      runStart = 0
    }
  }

  const last = samples[samples.length - 1]
  const elapsedMs = consecutive > 0 && last ? last.timestamp - runStart : 0

  const timeMet = elapsedMs >= DRIFT_TIME_THRESHOLD_MS
  const consecutiveMet = consecutive >= DRIFT_CONSECUTIVE_THRESHOLD
  const reason: DriftReason | undefined = timeMet
    ? consecutiveMet
      ? 'both'
      : 'time'
    : consecutiveMet
      ? 'consecutive'
      : undefined

  return {
    drifting: timeMet && consecutiveMet,
    reason,
    distanceMeters,
    consecutive,
    elapsedMs,
  }
}
