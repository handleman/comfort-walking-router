/**
 * Walk-mode UI state stores (spec 007, T6/T7).
 *
 * `walkMode` tracks whether walk mode is active, the route being walked, the
 * live marker position, and the off-route reroute warning (AC-4/AC-5);
 * `autoCenter` and `followPaused` control camera follow behavior (AC-1, AC-6).
 */

import { get, writable } from 'svelte/store'
import { checkArrival } from './navigation/arrival'
import { compareReroutes } from './navigation/rerouteChoice'
import type { RerouteChoice, RerouteVerdict, RouteForChoice } from './navigation/rerouteChoice'
import type { LatLng } from './navigation/interpolate'

/** Milliseconds a dismissed reroute warning stays snoozed (AC-5). */
export const REROUTE_SNOOZE_MS = 60_000

export interface WalkModeState {
  active: boolean
  route: LatLng[] | null
  markerPos: LatLng | null
  /** Final coordinate of the current route; the reroute target (AC-5). */
  destination: LatLng | null
  /** True while the sustained-drift "Off route — reroute?" banner shows (AC-4). */
  rerouteWarning: boolean
  /** Latest off-route distance in meters, shown in the banner (AC-4). */
  offRouteMeters: number
  /** True once the walker has arrived at the destination (AC-7). */
  arrived: boolean
  /** Distance delta (meters) of the chosen reroute vs the current route (spec 029, AC-2). */
  delta?: number
  /** Remaining distance (km) of the chosen reroute (spec 029, AC-2). */
  remainingKm?: number
  /** Comparison verdict for the last reroute decision (spec 029, AC-2). */
  verdict?: RerouteVerdict
}

export const walkMode = writable<WalkModeState>({
  active: false,
  route: null,
  markerPos: null,
  destination: null,
  rerouteWarning: false,
  offRouteMeters: 0,
  arrived: false,
})

export const autoCenter = writable<boolean>(true)

export const followPaused = writable<boolean>(false)

/** Error message shown when a reroute attempt fails (AC-5). */
export const rerouteError = writable<string | null>(null)

/** Timestamp until which reroute warnings are snoozed (AC-5). */
export const snoozedUntil = writable<number | null>(null)

let currentProfile: RouteForChoice['profile'] = []

function metresBetween(a: LatLng, b: LatLng): number {
  const latDiff = (b[0] - a[0]) * 111_320
  const lngDiff = (b[1] - a[1]) * 111_320 * Math.cos(((a[0] + b[0]) / 2) * (Math.PI / 180))
  return Math.hypot(latDiff, lngDiff)
}

function distanceAlong(route: LatLng[], pos: LatLng): number {
  let nearestIdx = 0
  let nearestDist = Infinity
  for (let i = 0; i < route.length; i++) {
    const d = metresBetween(route[i], pos)
    if (d < nearestDist) {
      nearestDist = d
      nearestIdx = i
    }
  }
  let total = 0
  for (let i = 0; i < nearestIdx; i++) {
    total += metresBetween(route[i], route[i + 1])
  }
  return total
}

export function start(route: LatLng[]): void {
  walkMode.set({
    active: true,
    route,
    markerPos: route[0] ?? null,
    destination: route.length > 0 ? route[route.length - 1] : null,
    rerouteWarning: false,
    offRouteMeters: 0,
    arrived: false,
  })
}

export function stop(): void {
  walkMode.set({
    active: false,
    route: null,
    markerPos: null,
    destination: null,
    rerouteWarning: false,
    offRouteMeters: 0,
    arrived: false,
    delta: undefined,
    remainingKm: undefined,
    verdict: undefined,
  })
  snoozedUntil.set(null)
  rerouteError.set(null)
  currentProfile = []
}

export function onFix(lat: number, lng: number): void {
  walkMode.update((s) => ({ ...s, markerPos: [lat, lng] }))
  if (get(autoCenter)) {
    followPaused.set(false)
  }
  walkMode.update((s) => {
    if (!s.active || !s.destination) return s
    const status = checkArrival(
      { position: [lat, lng], accuracyMeters: 0, timestampMs: 0 },
      s.destination,
    )
    if (!status.arrived) return s
    return { ...s, active: false, arrived: true }
  })
}

/** Raise the off-route warning once drift is sustained (AC-4). */
export function flagOffRoute(meters: number): void {
  walkMode.update((s) => ({ ...s, rerouteWarning: true, offRouteMeters: meters }))
}

/** Clear the off-route warning once the device is back on route (AC-5). */
export function clearRerouteWarning(): void {
  walkMode.update((s) => ({ ...s, rerouteWarning: false, offRouteMeters: 0 }))
}

/** Snooze the warning until back-on-route or 60 s (AC-5). */
export function dismissRerouteWarning(): void {
  snoozedUntil.set(Date.now() + REROUTE_SNOOZE_MS)
  walkMode.update((s) => ({ ...s, rerouteWarning: false }))
}

/**
 * Requery `POST /route` from the current position to the same destination and
 * replace the displayed route on success (AC-5).
 */
export async function reroute(pos: LatLng | null, dest: LatLng | null): Promise<void> {
  if (!pos || !dest) return
  try {
    const response = await fetch('/route', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ start: `${pos[0]},${pos[1]}`, end: `${dest[0]},${dest[1]}` }),
    })
    const data = await response.json()
    if (!response.ok) {
      throw new Error(data.message || data.detail || `Route request failed (${response.status})`)
    }
    const coords: [number, number][] = data.geometry?.coordinates ?? []
    const next: LatLng[] = coords.map(([lat, lng]) => [lat, lng])
    if (next.length === 0) {
      throw new Error('Reroute returned an empty route')
    }
    // The comparison baseline is the stored walk route, projected from the
    // walker position onto that route/profile — never the fresh candidate.
    const storedRoute = get(walkMode).route ?? next
    const alongM = distanceAlong(storedRoute, pos)
    const current: RouteForChoice = {
      profile: currentProfile,
      distance_m: alongM,
      from_m: alongM,
    }
    const candidateProfile = Array.isArray(data.comfort_profile) ? data.comfort_profile : []
    const candidate: RouteForChoice = {
      profile: candidateProfile,
      distance_m: Number(data.distance_m ?? 0),
      from_m: 0,
    }
    // No profile on either side means there is nothing to compare: a walker who
    // has drifted must never be stuck on the old route because comfort data is
    // missing, so that case keeps 007's behaviour (adopt). `compareReroutes`
    // failures (bad data) fall back the same way.
    let choice: RerouteChoice = {
      delta: 0,
      remainingKm: 0,
      verdict: 'replace',
      summary: '',
    }
    try {
      choice =
        current.profile.length && candidate.profile.length
          ? compareReroutes(current, candidate)
          : choice
    } catch {
      /* fall through to adopt */
    }
    if (choice.verdict === 'replace') {
      currentProfile = candidate.profile
      rerouteError.set(null)
      snoozedUntil.set(null)
      walkMode.update((s) => ({
        ...s,
        route: next,
        rerouteWarning: false,
        offRouteMeters: 0,
        delta: undefined,
        remainingKm: undefined,
        verdict: undefined,
      }))
    } else if (choice.verdict === 'ask') {
      walkMode.update((s) => ({
        ...s,
        rerouteWarning: true,
        delta: choice.delta,
        remainingKm: choice.remainingKm,
        verdict: choice.verdict,
      }))
    } else {
      walkMode.update((s) => ({
        ...s,
        rerouteWarning: true,
        delta: choice.delta,
        remainingKm: choice.remainingKm,
        verdict: choice.verdict,
      }))
      rerouteError.set(choice.summary)
    }
  } catch (err) {
    rerouteError.set(err instanceof Error ? err.message : String(err))
  }
}
