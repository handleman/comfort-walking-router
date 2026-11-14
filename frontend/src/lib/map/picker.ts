// Map pick-mode helpers (spec 014-walk-guidance-ux, task T6, AC-3).
// Pure role-toggle logic plus the reverse-geocode label client used by the
// Start/End pick buttons in App.svelte. No DOM or Leaflet imports here:
// everything is headlessly testable.

/** Which endpoint input a map pick targets. */
export type PickRole = 'start' | 'end'

/** A confirmed map pick: role, coordinates, and the reverse-geocoded label. */
export interface PickedLocation {
  role: PickRole
  lat: number
  lng: number
  label: string
}

/**
 * Toggle the active pick role: clicking the already-active role cancels
 * pick mode (null); clicking the other role switches to it.
 */
export function togglePickRole(current: PickRole | null, role: PickRole): PickRole | null {
  return current === role ? null : role
}

/** Crosshair-mode hint shown while the given pick role is active. */
export function pickHint(role: PickRole): string {
  return role === 'start'
    ? 'Click the map to set the start point (Esc to cancel)'
    : 'Click the map to set the end point (Esc to cancel)'
}

/**
 * Reverse geocode coordinates into a human-readable label via
 * GET /geocode/reverse. Throws on a non-OK response; falls back to the
 * formatted "lat, lng" pair when the result list is empty.
 */
export async function reverseLabel(lat: number, lng: number): Promise<string> {
  const res = await fetch(
    '/geocode/reverse?lat=' + lat.toFixed(5) + '&lng=' + lng.toFixed(5) + '&limit=1',
  )
  if (!res.ok) {
    throw new Error('reverse geocode failed: ' + res.status)
  }
  const data: { results?: unknown } = await res.json()
  const results = Array.isArray(data?.results) ? data.results : []
  const first = results[0] as { label?: unknown } | undefined
  const label = typeof first?.label === 'string' ? first.label : ''
  if (label) return label
  return lat.toFixed(5) + ', ' + lng.toFixed(5)
}
