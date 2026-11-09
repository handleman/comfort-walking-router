/**
 * Pure helpers for walking a position along a route LineString (spec 007, T1).
 *
 * Coordinates are `[lat, lng]` pairs; all distances are meters. The tick source
 * is injected so movement is fully deterministic in tests and the simulated
 * walk demo — no clock, no GPS, no randomness (AC-2, AC-8).
 */

export type LatLng = readonly [number, number]

const EARTH_RADIUS_M = 6_371_000

function toRadians(deg: number): number {
  return (deg * Math.PI) / 180
}

/** Great-circle distance in meters between two `[lat, lng]` points. */
export function haversineMeters(a: LatLng, b: LatLng): number {
  const dLat = toRadians(b[0] - a[0])
  const dLng = toRadians(b[1] - a[1])
  const lat1 = toRadians(a[0])
  const lat2 = toRadians(b[0])
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(h)))
}

/** Point at `ratio` (0..1) of the way from `a` to `b` in coordinate space. */
function lerpPoint(a: LatLng, b: LatLng, ratio: number): LatLng {
  return [a[0] + (b[0] - a[0]) * ratio, a[1] + (b[1] - a[1]) * ratio]
}

/**
 * The `[lat, lng]` reached after `ticks()` ticks, each advancing
 * `distanceMeters` along `line` from its first to its last coordinate.
 *
 * - `ticks` is the injected tick source (e.g. `() => tickCount` from the
 *   position provider); total distance walked is `distanceMeters * ticks()`.
 * - A target past the end of the line clamps to the last coordinate.
 * - Returns `null` for an empty line; a single-point line returns that point.
 */
export function interpolateAlongLineString(
  line: readonly LatLng[],
  distanceMeters: number,
  ticks: () => number,
): LatLng | null {
  const first = line[0]
  if (!first) return null
  if (line.length === 1) return [first[0], first[1]]

  const target = Math.max(0, distanceMeters * ticks())
  let walked = 0
  for (let i = 1; i < line.length; i++) {
    const a = line[i - 1]
    const b = line[i]
    if (!a || !b) continue
    const segLen = haversineMeters(a, b)
    if (segLen <= 0) continue
    if (walked + segLen >= target) {
      return lerpPoint(a, b, (target - walked) / segLen)
    }
    walked += segLen
  }

  const last = line[line.length - 1]
  if (!last) return null
  return [last[0], last[1]]
}
