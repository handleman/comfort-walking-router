import { describe, expect, it } from 'vitest'

import type { LatLng } from '../navigation/interpolate'
import {
  initialPositionState,
  statusLabel,
  transition,
  type PositionEvent,
  type PositionEventData,
  type PositionState,
} from './current'

/** Coordinates are `[lat, lng]` tuples, matching the `LatLng` contract. */
const COORDS: LatLng = [47.6062, -122.3321]

/** One dispatched step: an event plus its optional data. */
type Step = { event: PositionEvent; data?: PositionEventData }

/** Shorthand: dispatch a sequence of events from `initialPositionState`. */
function run(...events: Step[]): PositionState {
  return events.reduce(
    (state, step) => transition(state, step.event, step.data ?? {}),
    initialPositionState,
  )
}

describe('position state machine (spec 014, T4)', () => {
  it('starts idle with empty context', () => {
    expect(initialPositionState.name).toBe('idle')
    expect(initialPositionState.context).toEqual({ coords: null, error: null, timestamp: null })
  })

  it('walks idle → requesting → success and stores the fix', () => {
    const requesting = transition(initialPositionState, 'REQUEST')
    expect(requesting.name).toBe('requesting')
    expect(requesting.context).toEqual({ coords: null, error: null, timestamp: null })

    const success = transition(requesting, 'SUCCESS', { coords: COORDS, timestamp: 1700000000000 })
    expect(success.name).toBe('success')
    expect(success.context.coords).toEqual(COORDS)
    expect(success.context.timestamp).toBe(1700000000000)
    expect(success.context.error).toBeNull()
  })

  it.each([
    ['denial', 'Permission denied'],
    ['timeout', 'Timed out'],
    ['unsupported', 'Geolocation unsupported'],
  ])('moves requesting → error on %s', (_kind, message) => {
    const requesting = transition(initialPositionState, 'REQUEST')
    const error = transition(requesting, 'FAILURE', { error: message })
    expect(error.name).toBe('error')
    expect(error.context.error).toBe(message)
  })

  it('falls back to a default message when FAILURE carries none', () => {
    const error = run({ event: 'REQUEST' }, { event: 'FAILURE' })
    expect(error.name).toBe('error')
    expect(error.context.error).toBe('Location unavailable')
  })

  it('retries error → requesting, keeping the old error until a new fix', () => {
    const error = run({ event: 'REQUEST' }, { event: 'FAILURE', data: { error: 'Timed out' } })
    const retrying = transition(error, 'RETRY')
    expect(retrying.name).toBe('requesting')
    expect(retrying.context.error).toBe('Timed out')

    const recovered = transition(retrying, 'SUCCESS', { coords: COORDS, timestamp: 1 })
    expect(recovered.name).toBe('success')
    expect(recovered.context.error).toBeNull()
  })

  it('resets any state to idle with cleared context', () => {
    const states: PositionState[] = [
      initialPositionState,
      run({ event: 'REQUEST' }),
      run({ event: 'REQUEST' }, { event: 'SUCCESS', data: { coords: COORDS, timestamp: 1 } }),
      run({ event: 'REQUEST' }, { event: 'FAILURE', data: { error: 'Timed out' } }),
    ]
    for (const state of states) {
      const reset = transition(state, 'RESET')
      expect(reset.name).toBe('idle')
      expect(reset.context).toEqual({ coords: null, error: null, timestamp: null })
    }
  })

  it('ignores events that are invalid for the current state', () => {
    expect(transition(initialPositionState, 'SUCCESS')).toBe(initialPositionState)
    expect(transition(initialPositionState, 'RETRY')).toBe(initialPositionState)
    const requesting = run({ event: 'REQUEST' })
    expect(transition(requesting, 'REQUEST')).toBe(requesting)
  })

  it('exposes an accessible label for every state (AC-2)', () => {
    expect(statusLabel(initialPositionState)).toBe('Location not requested')
    expect(statusLabel(run({ event: 'REQUEST' }))).toBe('Finding your location')
    expect(
      statusLabel(run({ event: 'REQUEST' }, { event: 'SUCCESS', data: { coords: COORDS } })),
    ).toBe('Current location found')
    expect(
      statusLabel(
        run({ event: 'REQUEST' }, { event: 'FAILURE', data: { error: 'Permission denied' } }),
      ),
    ).toBe('Permission denied')
    expect(statusLabel(run({ event: 'REQUEST' }, { event: 'FAILURE' }))).toBe(
      'Location unavailable',
    )
  })
})
