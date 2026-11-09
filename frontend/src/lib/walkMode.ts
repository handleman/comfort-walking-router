/**
 * Walk-mode UI state stores (spec 007, T6/T7).
 *
 * `walkMode` tracks whether walk mode is active, the route being walked, the
 * live marker position, and the off-route reroute warning (AC-4/AC-5);
 * `autoCenter` and `followPaused` control camera follow behavior (AC-1, AC-6).
 */

import { get, writable } from 'svelte/store'
import { checkArrival } from './navigation/arrival'
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
  })
  snoozedUntil.set(null)
  rerouteError.set(null)
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
    rerouteError.set(null)
    snoozedUntil.set(null)
    walkMode.update((s) => ({ ...s, route: next, rerouteWarning: false, offRouteMeters: 0 }))
  } catch (err) {
    rerouteError.set(err instanceof Error ? err.message : String(err))
  }
}
