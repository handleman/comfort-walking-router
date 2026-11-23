/**
 * Geolocation-on-start helper (spec 040, T18 / AC-5).
 *
 * Requests the browser position once and resolves to either a fix
 * (coordinates plus a reverse-geocoded label via the existing
 * `reverseLabel` client) or a no-fix outcome (denied, unavailable,
 * unsupported, or timed out). Never throws: the caller decides whether
 * a no-fix outcome should open the start-location modal.
 */

import type { LatLng } from '../navigation/interpolate'
import { reverseLabel } from '../map/picker'

/** A resolved start fix: coordinates plus the reverse-geocoded label. */
export interface StartFix {
  kind: 'fix'
  coords: LatLng
  label: string
}

/** No fix could be obtained; `reason` is a short human-readable message. */
export interface NoFix {
  kind: 'no-fix'
  reason: string
}

/** Outcome of the start geolocation request. */
export type StartFixResult = StartFix | NoFix

/** Type guard: true when the outcome is a resolved fix. */
export function isStartFix(result: StartFixResult): result is StartFix {
  return result.kind === 'fix'
}

/** Timeout for the one-shot position request, in milliseconds. */
export const TIMEOUT_MS = 10_000

/**
 * Request the browser position once and resolve to a fix or a no-fix.
 *
 * Uses `navigator.geolocation.getCurrentPosition` with a 10s timeout and
 * resolves `{ kind: 'no-fix', reason }` for every failure path
 * (unsupported, denied, unavailable, timed out). On success it
 * reverse-geocodes the coordinates via `reverseLabel`; if that lookup
 * fails the fix is still returned with a coordinate fallback label.
 */
export function requestStartFix(
  geolocation: Geolocation | undefined = typeof navigator === 'undefined'
    ? undefined
    : navigator.geolocation,
): Promise<StartFixResult> {
  return new Promise((resolve) => {
    if (!geolocation) {
      resolve({ kind: 'no-fix', reason: 'Geolocation unsupported' })
      return
    }
    geolocation.getCurrentPosition(
      async (position) => {
        const coords: LatLng = [position.coords.latitude, position.coords.longitude]
        let label: string
        try {
          label = await reverseLabel(coords[0], coords[1])
        } catch {
          label = coords[0].toFixed(5) + ', ' + coords[1].toFixed(5)
        }
        resolve({ kind: 'fix', coords, label })
      },
      (err) => {
        const reason =
          err.code === err.PERMISSION_DENIED
            ? 'Permission denied'
            : err.code === err.POSITION_UNAVAILABLE
              ? 'Location unavailable'
              : 'Timed out'
        resolve({ kind: 'no-fix', reason })
      },
      { timeout: TIMEOUT_MS, maximumAge: 0 },
    )
  })
}
