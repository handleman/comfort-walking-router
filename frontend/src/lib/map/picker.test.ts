/**
 * Unit tests for map pick-mode helpers — spec 014 (walk guidance UX),
 * task T6 (AC-3). Exercises the real exports of ./picker with a stubbed
 * global fetch; no local re-declaration of the code under test.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  pickHint,
  reverseLabel,
  swapPickRoles,
  togglePickRole,
  type PickRole,
  type PickedLocation,
} from './picker'

describe('pick role toggle (spec 014, T6, AC-3)', () => {
  it('activates a role from idle', () => {
    expect(togglePickRole(null, 'start')).toBe('start')
  })

  it('cancels pick mode when the active role is clicked again', () => {
    expect(togglePickRole('start', 'start')).toBeNull()
  })

  it('switches roles when the other endpoint button is clicked', () => {
    expect(togglePickRole('start', 'end')).toBe('end')
  })
})

describe('pickHint', () => {
  it('mentions the target endpoint and the Esc cancel key', () => {
    const hints: Array<[PickRole, string]> = [
      ['start', 'start point'],
      ['end', 'end point'],
    ]
    for (const [role, fragment] of hints) {
      expect(pickHint(role)).toContain(fragment)
      expect(pickHint(role)).toContain('Esc')
    }
  })
})

describe('swapPickRoles (spec 040, T8, AC-2 — ↑↓ origin/destination swap)', () => {
  const start: PickedLocation = { role: 'start', lat: 52.52, lng: 13.405, label: 'Berlin' }
  const end: PickedLocation = { role: 'end', lat: 48.135, lng: 11.582, label: 'Munich' }

  it('exchanges start and end, keeping roles correct', () => {
    const { start: s, end: e } = swapPickRoles(start, end)
    expect(s).toEqual({ role: 'start', lat: 48.135, lng: 11.582, label: 'Munich' })
    expect(e).toEqual({ role: 'end', lat: 52.52, lng: 13.405, label: 'Berlin' })
  })

  it('does not mutate the inputs', () => {
    swapPickRoles(start, end)
    expect(start.label).toBe('Berlin')
    expect(end.label).toBe('Munich')
  })

  it('is an involution: swapping twice restores the original', () => {
    const once = swapPickRoles(start, end)
    expect(swapPickRoles(once.start, once.end)).toEqual({ start, end })
  })

  it('is a no-op when either side is unset', () => {
    expect(swapPickRoles(start, null)).toEqual({ start, end: null })
    expect(swapPickRoles(null, end)).toEqual({ start: null, end })
    expect(swapPickRoles(null, null)).toEqual({ start: null, end: null })
  })
})

describe('reverseLabel', () => {
  const originalFetch = globalThis.fetch
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn()
    globalThis.fetch = fetchMock as unknown as typeof fetch
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
    vi.restoreAllMocks()
  })

  it('GETs /geocode/reverse with 5-decimal coords and resolves to results[0].label', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ results: [{ label: 'Marienplatz, München' }] }),
    })

    await expect(reverseLabel(48.1, 11.5)).resolves.toBe('Marienplatz, München')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const url = String(fetchMock.mock.calls[0]?.[0])
    expect(url).toContain('/geocode/reverse')
    expect(url).toContain('lat=48.10000')
  })

  it('prefers the live `suggestions` contract when both fields are present', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        suggestions: [{ label: 'Untermenzing, Munich' }],
        results: [{ label: 'Legacy result' }],
      }),
    })

    await expect(reverseLabel(48.1, 11.5)).resolves.toBe('Untermenzing, Munich')
  })

  it('falls back to the legacy `results` contract when `suggestions` is absent', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ results: [{ label: 'Legacy result' }] }),
    })

    await expect(reverseLabel(48.1, 11.5)).resolves.toBe('Legacy result')
  })

  it('falls back to the coordinate pair when both result lists are empty', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ suggestions: [] }),
    })

    await expect(reverseLabel(48.1, 11.5)).resolves.toBe('48.10000, 11.50000')
  })

  it('rejects on a non-OK response', async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 502 })

    await expect(reverseLabel(48.1, 11.5)).rejects.toThrow('reverse geocode failed: 502')
  })
})
