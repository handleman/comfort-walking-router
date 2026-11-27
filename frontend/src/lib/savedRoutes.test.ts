import { afterEach, describe, expect, it, vi } from 'vitest'

import { saveRoute, toSavedRoute, type RouteSnapshot, type SavedRouteRow } from './savedRoutes'

const SNAPSHOT: RouteSnapshot = {
  name: 'Marienplatz, Munich',
  waypoints: [
    { lat: 48.1374, lng: 11.5755 },
    { lat: 48.1642, lng: 11.6056 },
  ],
  geometry: {
    type: 'LineString',
    coordinates: [
      [11.5755, 48.1374],
      [11.6056, 48.1642],
    ],
  },
  distance_m: 3723.8,
  duration_s: 2640,
  comfort_score: 72,
  explanation: ['3.72 km, about 44 min walking.'],
  applied_preference: 'cloudy',
  preference_source: 'auto',
  weather: { temperature: -1.5, cloudCover: 100 },
  comfort_profile: null,
  timestamp: '2026-11-27T00:00:00Z',
}

const ROW: SavedRouteRow = {
  id: 'route-1',
  holder_id: 'holder-1',
  request: { name: 'Marienplatz, Munich' },
  response: SNAPSHOT,
  created_at: '2026-11-27T00:00:00Z',
  last_accessed_at: '2026-11-27T01:00:00Z',
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('toSavedRoute', () => {
  it('adapts the persisted request/response row to the client shape', () => {
    const saved = toSavedRoute(ROW)

    expect(saved).toMatchObject({
      id: 'route-1',
      name: 'Marienplatz, Munich',
      snapshot: SNAPSHOT,
      created_at: '2026-11-27T00:00:00Z',
      updated_at: '2026-11-27T01:00:00Z',
    })
  })

  it('still accepts the legacy client row', () => {
    const saved = toSavedRoute({
      id: 'route-2',
      name: 'Legacy',
      snapshot: SNAPSHOT,
      created_at: '2026-11-27T00:00:00Z',
      updated_at: '2026-11-27T00:00:00Z',
    })

    expect(saved.name).toBe('Legacy')
    expect(saved.snapshot).toEqual(SNAPSHOT)
  })

  it('falls back to the response name when the request has none', () => {
    const saved = toSavedRoute({ ...ROW, request: {} })
    expect(saved.name).toBe('Marienplatz, Munich')
  })
})

describe('saveRoute', () => {
  it('posts {request,response} and maps the returned row', async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(JSON.stringify(ROW), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const saved = await saveRoute('Marienplatz, Munich', SNAPSHOT)

    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(JSON.parse(String(init.body))).toEqual({
      request: { name: 'Marienplatz, Munich' },
      response: SNAPSHOT,
    })
    expect(saved.id).toBe('route-1')
    expect(saved.snapshot).toEqual(SNAPSHOT)
  })
})
