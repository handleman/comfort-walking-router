// Search suggestion fetcher (spec 014-walk-guidance-ux, task T7, AC-4).
// Debounced, cancellable autocomplete client for the geocode/suggest endpoint.

/** A single normalized suggestion ready for a datalist/combobox. */
export interface Suggestion {
  label: string
  value: string
  lat: number
  lng: number
}

const DEBOUNCE_MS = 280
const MIN_QUERY_LENGTH = 2

/** Build a debounced, cancellable suggestion fetcher against `baseUrl`. */
export function createSuggestionFetcher(baseUrl: string): (q: string) => Promise<Suggestion[]> {
  let debounceTimer: ReturnType<typeof setTimeout> | null = null
  let abortController: AbortController | null = null
  let requestId = 0

  return function fetchSuggestions(q: string): Promise<Suggestion[]> {
    // Ignore queries shorter than the minimum length.
    if (q.trim().length < MIN_QUERY_LENGTH) {
      return Promise.resolve([])
    }

    // Cancel any in-flight request and reset the debounce window.
    if (abortController) abortController.abort()
    if (debounceTimer !== null) clearTimeout(debounceTimer)

    const id = ++requestId
    return new Promise<Suggestion[]>((resolve) => {
      debounceTimer = setTimeout(() => {
        abortController = new AbortController()
        fetch(`${baseUrl}/api/geocode/suggest?q=${encodeURIComponent(q)}`, {
          signal: abortController.signal,
        })
          .then((res) => (res.ok ? res.json() : Promise.resolve({ results: [] })))
          .then((data: { results?: unknown }) => {
            // Stale response guard: only the latest request id may resolve.
            if (id !== requestId) return
            resolve(normalizeSuggestions(data))
          })
          .catch(() => {
            // Aborted or network failure: resolve empty unless superseded.
            if (id === requestId) resolve([])
          })
      }, DEBOUNCE_MS)
    })
  }
}

/** Coerce an API payload into the normalized Suggestion shape. */
function normalizeSuggestions(data: { results?: unknown }): Suggestion[] {
  const results = Array.isArray(data?.results) ? data.results : []
  const out: Suggestion[] = []
  for (const raw of results) {
    if (typeof raw !== 'object' || raw === null) continue
    const r = raw as Record<string, unknown>
    const label = typeof r.label === 'string' ? r.label : ''
    const value = typeof r.value === 'string' ? r.value : label
    const lat = typeof r.lat === 'number' ? r.lat : Number(r.lat)
    const lng = typeof r.lng === 'number' ? r.lng : Number(r.lng)
    if (!label || !Number.isFinite(lat) || !Number.isFinite(lng)) continue
    out.push({ label, value, lat, lng })
  }
  return out
}
