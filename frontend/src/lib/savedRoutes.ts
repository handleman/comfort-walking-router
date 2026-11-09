// Saved routes client (spec 005-saved-routes, task T8)
// Types + token helpers + fetch wrappers for the saved-routes API.

/** A saved route as returned by the API. */
export interface SavedRoute {
  id: string
  name: string
  description?: string
  snapshot: RouteSnapshot
  created_at: string
  updated_at: string
}

/** User preferences persisted server-side. */
export interface Prefs {
  default_preference: string
  shade: number
  quiet: number
  greenery: number
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

/** POST a new saved route. */
export async function saveRoute(name: string, snapshot: RouteSnapshot): Promise<SavedRoute> {
  const res = await fetch('/api/saved-routes', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ name, snapshot }),
  })
  return handle<SavedRoute>(res)
}

/** GET all saved routes for this token. */
export async function listRoutes(): Promise<SavedRoute[]> {
  const res = await fetch('/api/saved-routes', { headers: authHeaders() })
  return handle<SavedRoute[]>(res)
}

/** GET a single saved route by id. */
export async function recallRoute(id: string): Promise<SavedRoute> {
  const res = await fetch(`/api/saved-routes/${encodeURIComponent(id)}`, { headers: authHeaders() })
  return handle<SavedRoute>(res)
}

/** DELETE a saved route by id. */
export async function deleteRoute(id: string): Promise<void> {
  const res = await fetch(`/api/saved-routes/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!res.ok) throw new Error(`saved-routes API error ${res.status}`)
}

/** GET the user's preferences. */
export async function getPrefs(): Promise<Prefs> {
  const res = await fetch('/api/prefs', { headers: authHeaders() })
  return handle<Prefs>(res)
}

/** PUT updated preferences. */
export async function updatePrefs(prefs: Prefs): Promise<Prefs> {
  const res = await fetch('/api/prefs', {
    method: 'PUT',
    headers: authHeaders(),
    body: JSON.stringify(prefs),
  })
  return handle<Prefs>(res)
}
