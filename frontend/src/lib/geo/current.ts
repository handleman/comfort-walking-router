/**
 * Position state machine for walk guidance (spec 014, T4).
 *
 * A tiny, pure finite state machine describing how the UI acquires the
 * walker's current position (AC-1) and what it announces while doing so
 * (AC-2). No clock, no GPS, no side effects: `transition()` takes a state
 * and an event and returns the next state, so tests and components stay
 * deterministic.
 *
 * States:  idle → requesting → success | error (error → requesting via RETRY)
 * Events:  REQUEST | SUCCESS | FAILURE | RETRY | RESET
 */

import type { LatLng } from '../navigation/interpolate'

/** All possible machine states. */
export type PositionStateName = 'idle' | 'requesting' | 'success' | 'error'

/** All events the machine understands. */
export type PositionEvent = 'REQUEST' | 'SUCCESS' | 'FAILURE' | 'RETRY' | 'RESET'

/** Data carried alongside an event (only the relevant fields are read). */
export interface PositionEventData {
  /** Fixed coordinates from the provider (SUCCESS). */
  coords?: LatLng
  /** Fix timestamp in ms since epoch (SUCCESS). */
  timestamp?: number
  /** Human-readable failure reason (FAILURE). */
  error?: string
}

/** Machine-wide data: the last fix, the last error, and when it happened. */
export interface PositionContext {
  coords: LatLng | null
  error: string | null
  timestamp: number | null
}

/** A full snapshot of the machine: which state, plus its context. */
export interface PositionState {
  name: PositionStateName
  context: PositionContext
}

/** Starting state before any position has been requested (AC-1). */
export const initialPositionState: PositionState = {
  name: 'idle',
  context: { coords: null, error: null, timestamp: null },
}

/**
 * Pure reducer: return the state reached from `state` on `event`.
 *
 * - `REQUEST`  idle → requesting
 * - `SUCCESS`  requesting → success (stores coords + timestamp, clears error)
 * - `FAILURE`  requesting → error (stores the error message)
 * - `RETRY`    error → requesting (keeps the old error until a new fix)
 * - `RESET`    any state → idle (clears context)
 *
 * Unhandled combinations return the state unchanged, so dispatching is
 * always safe.
 */
export function transition(
  state: PositionState,
  event: PositionEvent,
  data: PositionEventData = {},
): PositionState {
  switch (event) {
    case 'REQUEST':
      if (state.name === 'idle' || state.name === 'success') {
        return { name: 'requesting', context: { coords: null, error: null, timestamp: null } }
      }
      return state
    case 'SUCCESS':
      if (state.name === 'requesting') {
        return {
          name: 'success',
          context: { coords: data.coords ?? null, error: null, timestamp: data.timestamp ?? null },
        }
      }
      return state
    case 'FAILURE':
      if (state.name === 'requesting') {
        return {
          name: 'error',
          context: { ...state.context, error: data.error ?? 'Location unavailable' },
        }
      }
      return state
    case 'RETRY':
      if (state.name === 'error') {
        return {
          name: 'requesting',
          context: { coords: null, error: state.context.error, timestamp: null },
        }
      }
      return state
    case 'RESET':
      return initialPositionState
    default:
      return state
  }
}

/**
 * Accessible status label for a state, for `aria-live` announcement (AC-2).
 * Screen-reader friendly: short, present tense, no visual-only punctuation.
 */
export function statusLabel(state: PositionState): string {
  switch (state.name) {
    case 'idle':
      return 'Location not requested'
    case 'requesting':
      return 'Finding your location'
    case 'success':
      return 'Current location found'
    case 'error':
      return state.context.error ?? 'Location unavailable'
  }
}
