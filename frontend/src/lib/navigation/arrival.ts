/**
 * Arrival detection for the live position walk (spec 007, T4).
 *
 * Given a stream of position samples and a target point, decides whether the
 * walker has arrived — i.e. come within `ARRIVAL_RADIUS_M` meters of the
 * target. Like `./interpolate`, everything here is pure and deterministic:
 * time comes from the samples themselves, never from a clock (AC-2, AC-8).
 */

import { haversineMeters, type LatLng } from './interpolate'

/** Distance in meters from the target inside which the walker has arrived. */
export const ARRIVAL_RADIUS_M = 25

/**
 * Slack for the inclusive radius comparison. Haversine round-trips a
 * degree-derived offset through radians/sin/asin, so a fix placed exactly on
 * the 25 m boundary can compute a few ULPs above it (~1e-13 m). One nanometer
 * absorbs that rounding without meaningfully widening the radius.
 */
const ARRIVAL_EPSILON_M = 1e-9

/** Straight-line (haversine) distance in meters from `point` to `destination`. */
export function distanceToDestinationMeters(point: LatLng, destination: LatLng): number {
  return haversineMeters(point, destination)
}

/** One observed position fix feeding arrival detection. */
export interface ArrivalSample {
  /** Observed `[lat, lng]` position. */
  position: LatLng
  /** GPS accuracy radius in meters for this fix. */
  accuracyMeters: number
  /** Sample time in ms, taken from the fix (no clock reads). */
  timestampMs: number
}

/** Result of evaluating the latest sample against the arrival target. */
export interface ArrivalStatus {
  /** True once the walker is within `ARRIVAL_RADIUS_M` of the target. */
  arrived: boolean
  /** Distance in meters from the latest sample to the target. */
  distanceMeters: number
}

/**
 * Decide arrival from a single sample against the destination.
 *
 * Pure and stateless: no history, no clock, no side effects — calling it
 * repeatedly with the same sample always yields the same result (idempotent).
 */
export function checkArrival(sample: ArrivalSample, destination: LatLng): ArrivalStatus {
  const distanceMeters = distanceToDestinationMeters(sample.position, destination)
  return {
    arrived: distanceMeters <= ARRIVAL_RADIUS_M + ARRIVAL_EPSILON_M,
    distanceMeters,
  }
}
