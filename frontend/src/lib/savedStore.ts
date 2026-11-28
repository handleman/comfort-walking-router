// Local saved-routes store (spec 045-local-saved-routes, task T1)
// localStorage-backed save/list/delete for routes, plus a small preferences
// record. Reuses the existing RouteSnapshot / SavedRoute / Prefs shapes from
// savedRoutes.ts.

import type { SavedRoute, RouteSnapshot, Prefs } from './savedRoutes'

const LOCAL_ROUTES_KEY = 'swarm_local_saved_routes'
const LOCAL_PREFS_KEY = 'swarm_local_prefs'

/** Legacy keys used by earlier iterations of this spec. */
const LEGACY_ROUTES_KEYS = ['swarm_saved_walks', 'mellow_walk_saved_routes']

/** A locally-stored saved route keeps the public shape but adds a local id. */
export interface LocalSavedRoute extends SavedRoute {
  local: true
}

/** The stored collection shape; kept minimal and versioned by a key. */
interface StoredRouteCollection {
  routes: LocalSavedRoute[]
}

/**
 * Normalise one legacy record into a LocalSavedRoute. Legacy entries predate
 * the `local` flag (and may lack timestamps or a name), so any record with a
 * string `id` and a `snapshot` is accepted and upgraded; anything else is
 * dropped. Returns null for records that cannot be a saved route at all.
 */
function toLocalRoute(record: unknown): LocalSavedRoute | null {
  if (!record || typeof record !== 'object') return null
  const r = record as Partial<SavedRoute>
  if (typeof r.id !== 'string' || !r.snapshot) return null
  const now = new Date().toISOString()
  const created_at = typeof r.created_at === 'string' && r.created_at ? r.created_at : now
  return {
    ...(r as SavedRoute),
    id: r.id,
    name: typeof r.name === 'string' && r.name ? r.name : (r.snapshot.name ?? 'Saved route'),
    snapshot: r.snapshot,
    created_at,
    updated_at: typeof r.updated_at === 'string' && r.updated_at ? r.updated_at : created_at,
    local: true,
  }
}

function migrateLegacyRoutes(): LocalSavedRoute[] | null {
  try {
    for (const key of LEGACY_ROUTES_KEYS) {
      const raw = localStorage.getItem(key)
      if (!raw) continue
      const parsed = JSON.parse(raw) as unknown
      const candidates: unknown[] = Array.isArray(parsed)
        ? parsed
        : parsed &&
            typeof parsed === 'object' &&
            Array.isArray((parsed as StoredRouteCollection).routes)
          ? (parsed as StoredRouteCollection).routes
          : []
      const routes = candidates.map(toLocalRoute).filter((r): r is LocalSavedRoute => r !== null)
      // Only report a migration when something valid was found; returning
      // null lets readRoutes avoid persisting an empty collection over
      // un-migrated legacy data.
      if (routes.length > 0) return routes
    }
  } catch {
    /* ignore corrupt legacy data */
  }
  return null
}

function readRoutes(): LocalSavedRoute[] {
  try {
    const raw = localStorage.getItem(LOCAL_ROUTES_KEY)
    if (!raw) {
      const legacy = migrateLegacyRoutes()
      if (legacy) {
        writeRoutes(legacy)
        return legacy
      }
      return []
    }
    const parsed = JSON.parse(raw) as StoredRouteCollection
    return Array.isArray(parsed.routes) ? parsed.routes : []
  } catch {
    return []
  }
}

function writeRoutes(routes: LocalSavedRoute[]): void {
  try {
    const payload = JSON.stringify({ routes })
    localStorage.setItem(LOCAL_ROUTES_KEY, payload)
  } catch {
    /* storage unavailable or unserialisable; writes are silently ignored */
  }
}

/** Generate a short random id for a locally saved route. */
function makeLocalId(): string {
  const bytes = new Uint8Array(8)
  crypto.getRandomValues(bytes)
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
}

/** Persist a route locally. */
export function saveLocalRoute(name: string, snapshot: RouteSnapshot): LocalSavedRoute {
  const now = new Date().toISOString()
  const route: LocalSavedRoute = {
    id: makeLocalId(),
    name,
    snapshot,
    created_at: now,
    updated_at: now,
    local: true,
  }
  const routes = readRoutes()
  routes.unshift(route)
  writeRoutes(routes)
  return route
}

/** List all locally saved routes, newest first. */
export function listLocalRoutes(): LocalSavedRoute[] {
  return readRoutes()
}

/** Recall a single locally saved route by id, or null when absent. */
export function recallLocalRoute(id: string): LocalSavedRoute | null {
  return readRoutes().find((r) => r.id === id) ?? null
}

/** Delete a locally saved route by id. */
export function deleteLocalRoute(id: string): void {
  const routes = readRoutes().filter((r) => r.id !== id)
  writeRoutes(routes)
}

/** Default local preferences. Mirrors savedRoutes.ts NO_DB_PREFS. */
export const DEFAULT_LOCAL_PREFS: Prefs = {
  default_preference: '',
  shade: 0,
  quiet: 0,
  greenery: 0,
  prefer_lit: false,
  avoid_traffic: false,
}

/** Read local preferences from localStorage. */
export function getLocalPrefs(): Prefs {
  try {
    const raw = localStorage.getItem(LOCAL_PREFS_KEY)
    if (!raw) return DEFAULT_LOCAL_PREFS
    const parsed = JSON.parse(raw) as Partial<Prefs>
    return { ...DEFAULT_LOCAL_PREFS, ...parsed }
  } catch {
    return DEFAULT_LOCAL_PREFS
  }
}

/** Write local preferences to localStorage. Partial updates are merged with the
 *  currently stored preferences so callers can update a single setting.
 */
export function updateLocalPrefs(prefs: Partial<Prefs>): void {
  try {
    const merged = { ...getLocalPrefs(), ...prefs }
    const payload = JSON.stringify(merged)
    localStorage.setItem(LOCAL_PREFS_KEY, payload)
  } catch {
    /* storage unavailable or unserialisable; writes are silently ignored */
  }
}

/** Reset local preferences to the default values. */
export function resetLocalPrefs(): void {
  updateLocalPrefs(DEFAULT_LOCAL_PREFS)
}
