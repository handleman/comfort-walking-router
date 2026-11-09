/**
 * Walk-mode UI state stores (spec 007, T6).
 *
 * `walkMode` tracks whether walk mode is active, the route being walked, and
 * the live marker position; `autoCenter` and `followPaused` control camera
 * follow behavior (AC-1, AC-6).
 */

import { get, writable } from 'svelte/store'
import type { LatLng } from './navigation/interpolate'

export interface WalkModeState {
  active: boolean
  route: LatLng[] | null
  markerPos: LatLng | null
}

export const walkMode = writable<WalkModeState>({
  active: false,
  route: null,
  markerPos: null,
})

export const autoCenter = writable<boolean>(true)

export const followPaused = writable<boolean>(false)

export function start(route: LatLng[]): void {
  walkMode.set({ active: true, route, markerPos: route[0] })
}

export function stop(): void {
  walkMode.set({ active: false, route: null, markerPos: null })
}

export function onFix(lat: number, lng: number): void {
  walkMode.update((s) => ({ ...s, markerPos: [lat, lng] }))
  if (get(autoCenter)) {
    followPaused.set(false)
  }
}

/** Toggle auto-centering; switching it back on clears any follow pause (AC-1). */
export function toggleAutoCenter(): void {
  autoCenter.update((v) => !v)
  if (get(autoCenter)) {
    followPaused.set(false)
  }
}

/** Pause camera follow (e.g. after a manual pan) while auto-center stays on (AC-6). */
export function pauseFollow(): void {
  if (get(autoCenter)) {
    followPaused.set(true)
  }
}

/** Resume camera follow (AC-6). */
export function resumeFollow(): void {
  followPaused.set(false)
}
