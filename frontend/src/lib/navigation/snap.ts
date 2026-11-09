/**
 * Spherical helpers for snapping a live position onto a route (spec 007, T2).
 *
 * Coordinates are `[lat, lng]` pairs, matching `./interpolate`. All distances
 * are meters and all angles are degrees unless a name says otherwise. These
 * helpers are pure and deterministic so tests can assert exact values (AC-4).
 */

import { haversineMeters, type LatLng } from './interpolate'

export type { LatLng }

const EARTH_RADIUS_M = 6_371_000

/** Convert degrees to radians. */
export function toRadians(deg: number): number {
  return (deg * Math.PI) / 180
}

/** Convert radians to degrees. */
function toDegrees(rad: number): number {
  return (rad * 180) / Math.PI
}

/** Normalize a bearing in degrees to 0..360. */
function normalizeBearing(deg: number): number {
  return ((deg % 360) + 360) % 360
}

/**
 * Initial bearing (forward azimuth) in degrees from `a` to `b`, 0 = north,
 * clockwise, normalized to 0..360.
 */
export function bearing(a: LatLng, b: LatLng): number {
  const lat1 = toRadians(a[0])
  const lat2 = toRadians(b[0])
  const dLng = toRadians(b[1] - a[1])
  const y = Math.sin(dLng) * Math.cos(lat2)
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLng)
  return normalizeBearing(toDegrees(Math.atan2(y, x)))
}

/**
 * The `[lat, lng]` reached from `start` after traveling `distanceMeters`
 * along the great circle with initial `bearingDeg` (degrees, 0 = north).
 */
export function destinationPoint(
  start: LatLng,
  bearingDeg: number,
  distanceMeters: number,
): LatLng {
  const angular = distanceMeters / EARTH_RADIUS_M
  const lat1 = toRadians(start[0])
  const lng1 = toRadians(start[1])
  const theta = toRadians(bearingDeg)

  const sinLat2 =
    Math.sin(lat1) * Math.cos(angular) + Math.cos(lat1) * Math.sin(angular) * Math.cos(theta)
  const lat2 = Math.asin(Math.min(1, Math.max(-1, sinLat2)))
  const lng2 =
    lng1 +
    Math.atan2(
      Math.sin(theta) * Math.sin(angular) * Math.cos(lat1),
      Math.cos(angular) - Math.sin(lat1) * sinLat2,
    )

  return [toDegrees(lat2), toDegrees(lng2)]
}

export { haversineMeters }

/** Result of snapping a fix onto one route segment. */
export interface SnapToSegmentResult {
  /** Closest point on segment `a→b` to `fix` (projection clamped to the segment). */
  point: LatLng
  /** Signed cross-track distance in meters (positive = right of `a→b`). */
  crossTrackMeters: number
  /** Echo of the segment index passed in. */
  segmentIndex: number
}

/**
 * Snap `fix` onto the great-circle segment from `a` to `b`: project the fix
 * along the segment bearing, clamp the along-track distance to
 * `[0, segment length]`, and report the resulting point, signed cross-track
 * distance, and segment index (AC-4).
 */
export function snapToSegment(
  fix: LatLng,
  a: LatLng,
  b: LatLng,
  segmentIndex: number,
): SnapToSegmentResult {
  const bearingAB = bearing(a, b)
  const bearingAF = bearing(a, fix)
  const d13 = haversineMeters(a, fix) / EARTH_RADIUS_M
  const theta13 = toRadians(bearingAF)
  const theta12 = toRadians(bearingAB)

  // Signed cross-track angle (radians), positive when fix is right of a→b.
  const sinXt = Math.sin(theta13 - theta12) * Math.sin(d13)
  const xtAngle = Math.asin(Math.min(1, Math.max(-1, sinXt)))
  const crossTrackMeters = xtAngle * EARTH_RADIUS_M

  // Along-track angular distance from `a` toward `b`.
  const cosAt = Math.cos(d13) / Math.cos(xtAngle)
  const atAngle = Math.acos(Math.min(1, Math.max(-1, cosAt)))
  const alongTrackMeters = atAngle * EARTH_RADIUS_M

  const segmentLength = haversineMeters(a, b)
  const clamped = Math.min(segmentLength, Math.max(0, alongTrackMeters))
  const point = destinationPoint(a, bearingAB, clamped)

  return { point, crossTrackMeters, segmentIndex }
}

/** Result of snapping a fix onto a whole route (polyline of `LatLng`). */
export interface SnapResult {
  /** Closest point on the route to `fix`. */
  snapped: LatLng
  /** Absolute off-route distance in meters from `fix` to `snapped`. */
  distanceOffRoute: number
  /** Index of the winning segment (`line[i] → line[i + 1]`). */
  segmentIndex: number
}

/**
 * Snap `fix` onto the route `line`: evaluate every segment with
 * `snapToSegment` and return the one with the smallest off-route distance
 * (AC-4). Returns `null` for an empty line; a single-point line snaps to
 * that point.
 */
export function snapToRoute(fix: LatLng, line: readonly LatLng[]): SnapResult | null {
  if (line.length === 0) return null
  if (line.length === 1) {
    return {
      snapped: line[0],
      distanceOffRoute: haversineMeters(fix, line[0]),
      segmentIndex: 0,
    }
  }

  let best: SnapResult | null = null
  for (let i = 0; i < line.length - 1; i++) {
    const a = line[i]
    const b = line[i + 1]
    const result =
      a[0] === b[0] && a[1] === b[1]
        ? { point: a, crossTrackMeters: haversineMeters(fix, a), segmentIndex: i }
        : snapToSegment(fix, a, b, i)
    const distance = Math.abs(result.crossTrackMeters)
    if (best === null || distance < Math.abs(best.distanceOffRoute)) {
      best = { snapped: result.point, distanceOffRoute: distance, segmentIndex: i }
    }
  }
  return best
}
