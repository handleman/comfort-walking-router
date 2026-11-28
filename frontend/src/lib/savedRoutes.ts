// Saved routes client (spec 005-saved-routes, task T8)
// Types + token helpers + fetch wrappers for the saved-routes API.

import type { ComfortProfileSegment } from './map/comfortBands'

/** A saved route as returned by the API. */
export interface SavedRoute {
  id: string
  name: string
  description?: string
  snapshot: RouteSnapshot
  created_at: string
  updated_at: string
}

/**
 * The persisted row as the API returns it (spec 005 T7): the database stores
 * the original request and the route response, not the client's `snapshot`
 * shape. `toSavedRoute` is the one adapter between the two.
 */
export interface SavedRouteRow {
  id: string
  holder_id?: string
  request?: { name?: string; description?: string } & Record<string, unknown>
  response?: RouteSnapshot & { name?: string; description?: string }
  created_at?: string
  last_accessed_at?: string
  /** Legacy/hand-written client shape; accepted so a stale deployment is safe. */
  name?: string
  description?: string
  snapshot?: RouteSnapshot
  updated_at?: string
}

/** Map an API row (request/response) or a legacy client row to `SavedRoute`. */
export function toSavedRoute(row: SavedRouteRow): SavedRoute {
  const snapshot = (row.snapshot ?? row.response) as RouteSnapshot
  const name =
    row.name ??
    row.request?.name ??
    (row.response as { name?: string } | undefined)?.name ??
    snapshot?.name ??
    'Saved route'
  const description =
    row.description ??
    row.request?.description ??
    (row.response as { description?: string } | undefined)?.description
  return {
    id: row.id,
    name,
    ...(description ? { description } : {}),
    snapshot,
    created_at: row.created_at ?? '',
    updated_at: row.updated_at ?? row.last_accessed_at ?? row.created_at ?? '',
  }
}

/** User preferences persisted server-side. */
export interface Prefs {
  default_preference: string
  shade: number
  quiet: number
  greenery: number
  prefer_lit: boolean
  avoid_traffic: boolean
}

/** The route payload captured when a route is saved. */
export interface RouteSnapshot {
  name: string
  waypoints: { lat: number; lng: number }[]
  geometry: { type: 'LineString'; coordinates: [number, number][] }
  distance_m: number
  duration_s: number
  comfort_score: number
  explanation: string[]
  applied_preference: string
  preference_source: 'auto' | 'manual'
  weather: { temperature: number; cloudCover: number }
  comfort_profile: ComfortProfileSegment[] | null
  timestamp: string
}

const TOKEN_KEY = 'swarm_saved_routes_token'

/** Return the stored token, or null if none was minted yet. */
export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

/** Mint a 128-bit hex token into localStorage on first run; return it. */
export function ensureToken(): string {
  const existing = getToken()
  if (existing) return existing
  const bytes = new Uint8Array(16) // 128 bits
  crypto.getRandomValues(bytes)
  const token = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
  try {
    localStorage.setItem(TOKEN_KEY, token)
  } catch {
    /* storage unavailable; token stays session-only */
  }
  return token
}

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  return { 'Content-Type': 'application/json', Authorization: `Bearer ${ensureToken()}`, ...extra }
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`saved-routes API error ${res.status}`)
  return (await res.json()) as T
}

// 503 = the saved-routes feature is off (no DATABASE_URL). Treat it as "nothing
// saved yet", not an error, so a free deployment without a database is clean.
const SERVICE_UNAVAILABLE = 503

const NO_DB_PREFS: Prefs = {
  default_preference: '',
  shade: 0,
  quiet: 0,
  greenery: 0,
  prefer_lit: false,
  avoid_traffic: false,
}

/** Feature flags from `GET /capabilities` (043 T1). */
export interface Capabilities {
  saved_routes: boolean
  database: boolean
}

/**
 * Whether the saved-routes feature is on. Cached after the first
 * `/capabilities` probe so the UI hides Saved without a per-render fetch.
 */
let savedAvailable: boolean | null = null

/** GET /capabilities; true when the saved-routes feature is available. */
export async function isSavedAvailable(): Promise<boolean> {
  if (savedAvailable !== null) return savedAvailable
  try {
    const res = await fetch('/capabilities')
    const caps = (await res.json()) as Partial<Capabilities>
    savedAvailable = caps.saved_routes === true
  } catch {
    savedAvailable = false
  }
  return savedAvailable
}

/** Test hook: reset the cached capability probe. */
export function resetSavedAvailable(): void {
  savedAvailable = null
}

/** POST a new saved route. */
export async function saveRoute(name: string, snapshot: RouteSnapshot): Promise<SavedRoute> {
  const res = await fetch('/saved-routes', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ request: { name }, response: snapshot }),
  })
  return toSavedRoute(await handle<SavedRouteRow>(res))
}

/** GET all saved routes for this token. */
export async function listRoutes(): Promise<SavedRoute[]> {
  const res = await fetch('/saved-routes', { headers: authHeaders() })
  if (res.status === SERVICE_UNAVAILABLE) return []
  const rows = await handle<SavedRouteRow[]>(res)
  return rows.map(toSavedRoute)
}

/** GET a single saved route by id. */
export async function recallRoute(id: string): Promise<SavedRoute> {
  const res = await fetch(`/saved-routes/${encodeURIComponent(id)}`, { headers: authHeaders() })
  return toSavedRoute(await handle<SavedRouteRow>(res))
}

/** DELETE a saved route by id. */
export async function deleteRoute(id: string): Promise<void> {
  const res = await fetch(`/saved-routes/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!res.ok) throw new Error(`saved-routes API error ${res.status}`)
}

/** GET the user's preferences. */
export async function getPrefs(): Promise<Prefs> {
  const res = await fetch('/saved-routes/prefs', { headers: authHeaders() })
  if (res.status === SERVICE_UNAVAILABLE) return NO_DB_PREFS
  return handle<Prefs>(res)
}

/** PUT updated preferences. */
export async function updatePrefs(prefs: Prefs): Promise<Prefs> {
  const res = await fetch('/saved-routes/prefs', {
    method: 'PUT',
    headers: authHeaders(),
    body: JSON.stringify(prefs),
  })
  return handle<Prefs>(res)
}
