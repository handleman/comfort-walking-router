<script lang="ts">
  interface Waypoint {
    lat: number
    lng: number
  }

  interface LineStringGeometry {
    type: 'LineString'
    coordinates: [number, number][]
  }

  interface Weather {
    temperature: number
    cloudCover?: number
    // The API serializes the Open-Meteo field in snake_case; keep both so the
    // advice copy works against live, cached and saved payloads.
    cloud_cover?: number
  }

  interface Route {
    id: string
    name: string
    description?: string
    waypoints: Waypoint[]
    status: 'active' | 'inactive' | 'archived'
    timestamp: string
    comfort_score: number
    explanation: string[]
    geometry: LineStringGeometry
    distance_m: number
    comfort_profile: ComfortProfileSegment[] | null
    duration_s: number
    applied_preference: string
    preference_source: 'auto' | 'manual'
    weather: Weather
    attribution?: string
  }

  import { onMount } from 'svelte'
  import L from 'leaflet'
  import { personIcon, startPinIcon, endPinIcon } from './lib/map/icons'
  import { materialPaths } from './lib/map/material'
  import { checkArrival } from './lib/navigation/arrival'
  import type { ArrivalSample, ArrivalStatus } from './lib/navigation/arrival'
  import type { LatLng } from './lib/navigation/interpolate'
  import {
    clearRerouteWarning,
    flagOffRoute,
    onFix,
    start as startWalk,
    walkMode,
  } from './lib/walkMode'
  import { DRIFT_DISTANCE_THRESHOLD_M, distanceToRouteMeters } from './lib/navigation/drift'
  import ArrivalCard from './lib/components/ArrivalCard.svelte'
  import Attribution from './lib/components/Attribution.svelte'
  import TopSearchCard from './lib/components/TopSearchCard.svelte'
  import BottomDrawer from './lib/components/BottomDrawer.svelte'
  import ComfortPanel from './lib/components/ComfortPanel.svelte'
  import PreferencesSheet from './lib/components/PreferencesSheet.svelte'
  import RouteCard from './lib/components/RouteCard.svelte'
  import WalkControls from './lib/WalkControls.svelte'
  import StartLocationModal from './lib/components/StartLocationModal.svelte'
  import type { Suggestion } from './lib/search/suggestions'
  import { pickHint, reverseLabel, togglePickRole } from './lib/map/picker'
  import type { PickRole } from './lib/map/picker'
  import {
    COMFORT_BANDS,
    COMFORT_UNAVAILABLE_TEXT,
    bandColour,
    formatRun,
    mergeBandRuns,
  } from './lib/map/comfortBands'
  import type { ComfortBandRun, ComfortProfileSegment } from './lib/map/comfortBands'
  import {
    deleteRoute,
    ensureToken,
    getPrefs,
    listRoutes,
    recallRoute,
    saveRoute,
    updatePrefs,
  } from './lib/savedRoutes'
  import type { Prefs, SavedRoute } from './lib/savedRoutes'

  function formatArrivalTime(durationS: number): string {
    const arrival = new Date(Date.now() + durationS * 1000)
    return arrival.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  // Terrain: dominant comfort-profile factor by covered distance, falling back
  // to the applied preference when no profile data is available.
  function terrainLabel(r: Route): string {
    if (r.comfort_profile && r.comfort_profile.length > 0) {
      const covered = new Map<string, number>()
      for (const seg of r.comfort_profile) {
        covered.set(seg.factor, (covered.get(seg.factor) ?? 0) + (seg.to_m - seg.from_m))
      }
      let best = 'unknown'
      let bestLen = -1
      covered.forEach((len, factor) => {
        if (len > bestLen) {
          bestLen = len
          best = factor
        }
      })
      return best
    }
    return r.applied_preference
  }

  let currentStep: 'plan' | 'review' | 'walk' = 'plan'
  let mapElement: HTMLDivElement
  let map: L.Map | null = null
  let activePick: PickRole | null = null
  let pickBusy = false
  let pickError = ''
  let routeLayer: L.LayerGroup | null = null

  let start = ''
  let end = ''
  let route: Route | null = null
  let suggestionAttribution = ''
  let error = ''
  let savedRoutes: SavedRoute[] = []
  let prefs: Prefs | null = null
  let showPrefs = false
  // 041: the shade control is the design's single comfort preference.
  // `shadeManual` distinguishes an explicit choice from the weather auto-rule
  // (which sets the visible segment after a route but never overrides it).
  let shade: 'hot' | 'cloudy' | 'balanced' = 'balanced'
  let shadeManual = false
  let avoidTraffic = false
  let showPrefsSheet = false
  let showSavedWalks = false
  let showHowItWorks = false
  let savedError = ''
  let prefsError = ''
  let locateError = ''
  let didCenterOnUser = false
  // AC-5: opens when the start geolocation request fails with no fix.
  let startModalOpen = false
  // Set once the geolocation pre-fill has written the origin; afterwards a
  // manual origin (user-typed or map-picked) always wins and is never
  // overwritten by a later fix.
  let originPrefilled = false
  let currentMarker: L.Marker | null = null
  let walkerMarker: L.Marker | null = null
  let startCoords: [number, number] | null = null
  let endCoords: [number, number] | null = null
  let startMarker: L.Marker | null = null
  let endMarker: L.Marker | null = null
  let startSuggestion: Suggestion | null = null
  let endSuggestion: Suggestion | null = null
  // 042 AC-1/AC-2: map-pick builder state. A destination picked on the map
  // parks the planner (`awaitingBuild`) instead of firing POST /route, so the
  // bottom drawer can show the no-route builder until the user builds.
  let awaitingBuild = false
  // Set while the builder owns the drawer, so the auto-open effect never
  // fights the user's own collapse choice.
  let suppressAutoOpen = false
  // Controlled `open` for <BottomDrawer> once it is driven from here.
  let drawerOpen = false
  // True while the build request is in flight.
  let building = false

  // Keep the pinned waypoint coordinates and the attribution credit in sync
  // with the selected geocode suggestion (AC-8/AC-9): pin on selection, and
  // drop the pin when the text no longer matches the selection.
  $: if (startSuggestion && start === startSuggestion.label) {
    setStartCoords([startSuggestion.lat, startSuggestion.lng])
    suggestionAttribution = startSuggestion.attribution ?? ''
  } else if (startSuggestion) {
    startSuggestion = null
    clearStartCoords()
  }

  $: if (endSuggestion && end === endSuggestion.label) {
    // 042 AC-1/AC-2: a typed destination is not a hand-off to the builder —
    // clear the map-pick builder state so auto-planning (and the auto-open
    // drawer effect) runs normally for the chosen suggestion.
    awaitingBuild = false
    suppressAutoOpen = false
    building = false
    setEndCoords([endSuggestion.lat, endSuggestion.lng])
    suggestionAttribution = endSuggestion.attribution ?? ''
  } else if (endSuggestion) {
    endSuggestion = null
    clearEndCoords()
  }

  // Auto-plan (T16/T21, AC-8): whenever both endpoints are set, plan the route.
  // This is the ONLY /route trigger: no Find-route button and no manual
  // submit handler exists in the plan step (the ↑↓ swap stays bound to
  // swapEndpoints on TopSearchCard). Guarded so it never fires while either
  // endpoint is unset and never re-fires for the same coordinate pair (no loop).
  async function planRoute() {
    if (!startCoords || !endCoords) return
    error = ''
    try {
      const response = await fetch('/route', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          start,
          end,
          start_coords: startCoords,
          end_coords: endCoords,
          // 004/041: an explicit shade choice is the manual override; the
          // route contract now accepts `balanced` too. Without a choice, omit
          // the field so the weather auto-rule decides.
          ...(shadeManual ? { preference: shade } : {}),
          prefer_lit: prefs?.prefer_lit ?? false,
          avoid_traffic: avoidTraffic,
        }),
      })
      if (!response.ok) {
        let message = `Route planning failed (${response.status})`
        try {
          const data = await response.json()
          message = data.message ?? message
        } catch {
          // Keep the status-based message when the body is not JSON.
        }
        throw new Error(message)
      }
      route = (await response.json()) as Route
      drawRoute()
    } catch (err) {
      error = err instanceof Error ? err.message : String(err)
    }
  }

  let lastPlannedKey = ''
  // Reactive statement depends only on the coords; all reads/writes of
  // `lastPlannedKey` and `error` happen inside the plain function below,
  // so the reactive graph cannot loop on them.
  $: planAutoRoute(startCoords, endCoords)

  function planAutoRoute(a: LatLng | null, b: LatLng | null) {
    // 042 AC-1/AC-2: a map-picked destination parks the planner; the builder's
    // pill (handleBuildRoute) is the only trigger until the user builds.
    if (awaitingBuild) return
    const key = a && b ? `${a.join(',')}>${b.join(',')}` : ''
    if (!key) {
      // Either endpoint unset: never plan, forget the last pair so
      // re-entering the same pair later re-plans, and drop any stale
      // error left by a previous attempt.
      lastPlannedKey = ''
      error = ''
    } else if (key !== lastPlannedKey) {
      lastPlannedKey = key
      void planRoute()
    }
  }

  let arrival: ArrivalStatus | null = null
  let arrivalDismissed = false
  let sidebarCollapsed = false // desktop sidebar keeps its own toggle state
  let isDesktop = false // viewport state: which surface owns the controls (AC-3/AC-4)

  function evaluateArrival(sample: ArrivalSample) {
    if (!endCoords) return
    const destination: LatLng = [endCoords[0], endCoords[1]]
    arrival = checkArrival(sample, destination)
    if (arrival.arrived) arrivalDismissed = false
  }

  function dismissArrival() {
    arrivalDismissed = true
  }

  function planAnotherWalk() {
    arrivalDismissed = true
    arrival = null
    clearEndCoords()
    end = ''
  }

  function beginPick(role: PickRole) {
    activePick = togglePickRole(activePick, role)
    pickError = ''
    if (map) map.getContainer().classList.toggle('crosshair', activePick !== null)
  }

  function cancelPick() {
    activePick = null
    pickBusy = false
    pickError = ''
    if (map) map.getContainer().classList.remove('crosshair')
  }

  onMount(() => {
    // AC-3/AC-4: track the viewport breakpoint so only one surface renders
    // the controls at a time. The CSS uses the same 768px value, so the
    // drawer owns controls below 768px and the sidebar owns them at/above it.
    const desktopQuery = window.matchMedia('(min-width: 768px)')
    isDesktop = desktopQuery.matches
    const syncViewport = (event: MediaQueryListEvent) => {
      isDesktop = event.matches
    }
    desktopQuery.addEventListener('change', syncViewport)

    // Ordered bootstrap: the container exists here (Svelte has mounted it),
    // so create the map, wire the OSM tile layer onto it, and only then
    // attach observers/handlers. Leaflet caches the container's initial
    // dimensions, so force one re-measure right after the layer is added.
    map = L.map(mapElement).setView([48.137, 11.575], 12)
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map)
    // Ask the browser for the current position on start (AC-5) via
    // map.locate; this is non-blocking — the page stays usable while
    // permission is pending, and the first fix centres the map and
    // pre-fills the origin later (a manual origin overrides it).
    // 2026-11-26: a browser without the Geolocation API made map.locate()
    // throw inside onMount, so the start-location modal never opened and the
    // page looked broken. Ask for the origin instead.
    const hasGeolocation = Boolean(navigator.geolocation)
    if (hasGeolocation) {
      map.locate({ setView: false })
    } else {
      onLocationError({
        message: 'Geolocation is not available in this browser.',
      } as L.ErrorEvent)
    }
    // Defer to the next frame so the container has its final layout first.
    requestAnimationFrame(() => map?.invalidateSize())
    // Full-bleed map: re-measure whenever the viewport or overlay panel
    // changes the container's size (Leaflet caches the initial dimensions).
    const resizeObserver = new ResizeObserver(() => {
      map?.invalidateSize()
    })
    resizeObserver.observe(mapElement)
    ensureToken()
    // Continuous position fixes (spec 007, T10): watch geolocation from page
    // load so every fix fires `locationfound`, feeding onFix, the drift check,
    // and arrival detection for the whole walk, not just the first fix.
    if (hasGeolocation) {
      map.locate({ watch: true, setView: false, maxZoom: 16, enableHighAccuracy: true })
    }
    map.on('locationfound', onLocationFound)
    map.on('locationerror', onLocationError)
    map.on('click', onMapClick)
    loadSaved()
    loadPrefs()

    // Stop the watcher when a walk ends (Stop or arrival both clear `active`)
    // and re-arm it when a new walk starts, so fixes stay continuous while
    // walking and no duplicate geolocation watchers pile up.
    let wasWalkActive = false
    const unsubscribeWalkMode = walkMode.subscribe((state) => {
      if (!map) return
      if (state.active && !wasWalkActive) {
        currentStep = 'walk'
        map.stopLocate()
        map.locate({ watch: true, setView: false, maxZoom: 16, enableHighAccuracy: true })
      } else if (!state.active && wasWalkActive) {
        map.stopLocate()
      }
      wasWalkActive = state.active
    })
    return () => {
      desktopQuery.removeEventListener('change', syncViewport)
      unsubscribeWalkMode()
      map?.stopLocate()
      resizeObserver.disconnect()
      map?.remove()
      map = null
    }
  })

  async function loadSaved() {
    savedError = ''
    try {
      savedRoutes = await listRoutes()
    } catch (err) {
      savedError = err instanceof Error ? err.message : String(err)
    }
  }

  async function loadPrefs() {
    prefsError = ''
    try {
      prefs = await getPrefs()
      const saved = prefs.default_preference
      if (saved === 'hot' || saved === 'cloudy' || saved === 'balanced') {
        shade = saved
        shadeManual = true
      }
      avoidTraffic = prefs.avoid_traffic
    } catch (err) {
      prefsError = err instanceof Error ? err.message : String(err)
    }
  }

  async function onLocationFound(e: L.LocationEvent) {
    locateError = ''
    if (!map) return
    const { lat, lng } = e.latlng
    // Center once on the first fix, then keep the view where the user put it
    // (the watch must not yank the map around while they browse a route).
    if (!didCenterOnUser) {
      didCenterOnUser = true
      map.setView([lat, lng], 16)
      // A fix arriving after a denied/pending start request (AC-5): the
      // origin is now known, so the no-fix modal must not stay open.
      startModalOpen = false
      // Pre-fill the origin with the first fix (AC-5): reverse geocode to an
      // address, falling back to "lat, lng" if the lookup fails. A manually
      // chosen origin is left untouched because this branch only runs when no
      // origin is already set.
      if (!originPrefilled && !start && !startSuggestion) {
        // Fallback label matches reverseLabel's own empty-result fallback
        // (toFixed(5)) so the origin reads the same either way.
        const fallback = `${lat.toFixed(5)}, ${lng.toFixed(5)}`
        let label: string
        try {
          label = (await reverseLabel(lat, lng))?.trim() || fallback
        } catch {
          label = fallback
        }
        // The geocode is async: a manual origin may have been typed/selected
        // while we were waiting, so re-check before assigning so it is never
        // clobbered by this first-fix pre-fill.
        if (!start && !startSuggestion) {
          start = label
          setStartCoords([lat, lng])
        }
        // Guard the pre-fill: once applied (or once a manual origin exists),
        // later fixes must never overwrite the user's origin.
        originPrefilled = true
      } else {
        // A manual origin already exists: mark the pre-fill as settled so
        // later fixes can never overwrite it either.
        originPrefilled = true
      }
    }
    // Walk mode has its own marker (`syncWalker`); the pre-walk current
    // position marker would otherwise stack a second identical person icon on
    // top of it (014 AC-2 found two `.walk-person-marker` nodes).
    if ($walkMode.active) {
      if (currentMarker) {
        currentMarker.remove()
        currentMarker = null
      }
    } else if (currentMarker) {
      currentMarker.setLatLng([lat, lng])
    } else {
      currentMarker = L.marker([lat, lng], {
        icon: L.divIcon(personIcon()),
      }).addTo(map)
    }
    evaluateArrival({
      position: [lat, lng],
      accuracyMeters: e.accuracy,
      timestampMs: e.timestamp,
    })
    onFix(lat, lng)
    if ($walkMode.active && $walkMode.route) {
      const d = distanceToRouteMeters([lat, lng], $walkMode.route)
      if (d > DRIFT_DISTANCE_THRESHOLD_M) {
        flagOffRoute(d)
      } else {
        clearRerouteWarning()
      }
    }
  }

  function onLocationError(e: L.ErrorEvent) {
    locateError = e.message || 'Unable to determine your location.'
    // AC-5: a failed/denied start request with no fix must ask for the
    // origin. Once an origin is already chosen (fix pre-fill, typed
    // suggestion, or map pick) a later geolocation error never re-opens it.
    if (!originPrefilled && !start && !startSuggestion) {
      startModalOpen = true
    }
  }

  function handleStartChosen(suggestion: Suggestion) {
    start = suggestion.label
    startSuggestion = suggestion
    setStartCoords([suggestion.lat, suggestion.lng])
    originPrefilled = true
    startModalOpen = false
  }

  function handleStartPick() {
    beginPick('start')
    startModalOpen = false
  }

  function handleStartModalClose() {
    startModalOpen = false
  }

  function retryLocate() {
    locateError = ''
    map?.locate({ setView: true, maxZoom: 16 })
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && (showSavedWalks || showHowItWorks || showPrefsSheet)) {
      e.preventDefault()
      showSavedWalks = false
      showHowItWorks = false
      showPrefsSheet = false
      return
    }
    if (e.key === 'Escape' && activePick) {
      e.preventDefault()
      cancelPick()
    }
  }

  async function onMapClick(e: L.LeafletMouseEvent) {
    if (!activePick) return
    pickBusy = true
    try {
      const coords: [number, number] = [e.latlng.lat, e.latlng.lng]
      const role = activePick
      let label: string
      try {
        label = await reverseLabel(e.latlng.lat, e.latlng.lng)
      } catch (err) {
        // 042 AC-1: a destination pick still lands (with a coordinate
        // fallback label) when reverse geocoding has no name for the spot.
        if (role === 'start') throw err
        label = coords[0].toFixed(5) + ', ' + coords[1].toFixed(5)
      }
      if (role === 'start') {
        // A map-picked origin is manual: settle the geolocation pre-fill so a
        // later fix (or the in-flight first-fix geocode) never overwrites it.
        originPrefilled = true
        start = label
        setStartCoords(coords)
      } else {
        // 042 AC-1/AC-2: a map-picked destination parks the planner in the
        // build state — flags set and the controlled drawer opened *before*
        // setEndCoords so the builder renders against the new pin.
        end = label
        awaitingBuild = true
        suppressAutoOpen = true
        drawerOpen = true
        setEndCoords(coords)
      }
      cancelPick()
    } catch (err) {
      pickBusy = false
      pickError = err instanceof Error ? err.message : String(err)
    }
  }

  function setStartCoords(coords: [number, number]) {
    startCoords = coords
    if (startMarker) {
      startMarker.remove()
      startMarker = null
    }
    if (!map) return
    startMarker = L.marker(coords, { icon: L.divIcon(startPinIcon()) }).addTo(map)
  }

  function setEndCoords(coords: [number, number]) {
    endCoords = coords
    if (endMarker) {
      endMarker.remove()
      endMarker = null
    }
    if (!map) return
    endMarker = L.marker(coords, { icon: L.divIcon(endPinIcon()) }).addTo(map)
  }

  function clearStartCoords() {
    startCoords = null
    if (startMarker) {
      startMarker.remove()
      startMarker = null
    }
  }

  function clearEndCoords() {
    endCoords = null
    if (endMarker) {
      endMarker.remove()
      endMarker = null
    }
  }

  function syncWalker(pos: LatLng | null) {
    if (!pos || !$walkMode.active) {
      if (walkerMarker) {
        walkerMarker.remove()
        walkerMarker = null
      }
      return
    }
    if (!map) return
    if (walkerMarker) {
      walkerMarker.setLatLng([pos[0], pos[1]])
    } else {
      walkerMarker = L.marker([pos[0], pos[1]], { icon: L.divIcon(personIcon()) }).addTo(map)
    }
  }

  $: syncWalker($walkMode.markerPos)

  /** WalkControls route as `[lat, lng]` pairs; empty until a route exists. */
  $: walkRoute = route ? route.waypoints.map((w): LatLng => [w.lat, w.lng]) : []
  $: comfortRuns = route && route.comfort_profile ? mergeBandRuns(route.comfort_profile) : []

  function drawRoute() {
    if (!map || !route || !route.geometry) return
    if (routeLayer) {
      routeLayer.remove()
    }
    const layer = L.layerGroup().addTo(map)
    routeLayer = layer
    const runs: ComfortBandRun[] = route.comfort_profile ? mergeBandRuns(route.comfort_profile) : []
    const coords: [number, number][] = route.geometry.coordinates.map(
      (c) => [c[1], c[0]] as [number, number],
    )
    const dists: number[] = [0]
    for (let i = 1; i < coords.length; i++) {
      const [aLat, aLng] = coords[i - 1]
      const [bLat, bLng] = coords[i]
      const rad = Math.PI / 180
      const dLat = (bLat - aLat) * rad
      const dLng = (bLng - aLng) * rad
      const a =
        Math.sin(dLat / 2) ** 2 +
        Math.cos(aLat * rad) * Math.cos(bLat * rad) * Math.sin(dLng / 2) ** 2
      dists.push(dists[i - 1] + 2 * 6371000 * Math.asin(Math.sqrt(a)))
    }
    // Point on the route at a distance along it. The live geometry can be a
    // two-point overview, so a band slice that only keeps the original
    // vertices is empty (Leaflet draws `M0 0`); interpolate the band edges.
    const pointAtDistance = (d: number): [number, number] => {
      if (d <= 0) return coords[0]
      const total = dists[dists.length - 1]
      if (d >= total) return coords[coords.length - 1]
      let i = 1
      while (i < dists.length && dists[i] < d) i++
      const a = coords[i - 1]
      const b = coords[i]
      const span = dists[i] - dists[i - 1]
      const t = span > 0 ? (d - dists[i - 1]) / span : 0
      return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
    }
    let line: L.Polyline
    if (runs.length) {
      const lines: L.Polyline[] = []
      for (const run of runs) {
        const slice: [number, number][] = [pointAtDistance(run.from_m)]
        coords.forEach((c, i) => {
          if (dists[i] > run.from_m && dists[i] < run.to_m) slice.push(c)
        })
        slice.push(pointAtDistance(run.to_m))
        const pl = L.polyline(slice, { color: bandColour(run.band), weight: 6 })
          .bindTooltip(formatRun(run))
          .addTo(layer)
        lines.push(pl)
      }
      line = lines[0]
    } else {
      line = L.polyline(coords, { color: '#4a5568', weight: 6 }).addTo(layer)
    }
    const startPoint = route.waypoints[0]
    const endPoint = route.waypoints[1]
    if (startPoint) {
      L.marker([startPoint.lat, startPoint.lng], { icon: L.divIcon(startPinIcon()) })
        .bindTooltip('Start')
        .addTo(layer)
    }
    if (endPoint) {
      L.marker([endPoint.lat, endPoint.lng], { icon: L.divIcon(endPinIcon()) })
        .bindTooltip(end || 'Destination', {
          permanent: true,
          direction: 'top',
          offset: [0, -24],
          className: 'dest-callout',
        })
        .addTo(layer)
    }
    // 041: one honest route badge at the midpoint (duration + preference);
    // no second route badge because the API returns one route.
    const midPoint = pointAtDistance(dists[dists.length - 1] / 2)
    if (midPoint) {
      const badgePref =
        route.applied_preference === 'hot'
          ? 'More shade'
          : route.applied_preference === 'cloudy'
            ? 'More sun'
            : 'Balanced'
      const badgeSub = avoidTraffic ? `${badgePref} · Quieter` : badgePref
      const badge = `<div class="route-badge"><span class="route-badge-duration">${Math.round(
        route.duration_s / 60,
      )} min</span><span class="route-badge-sub">${badgeSub}</span></div>`
      L.marker(midPoint, {
        icon: L.divIcon({
          className: 'route-badge-icon',
          html: badge,
          iconSize: [140, 64],
          iconAnchor: [70, 32],
        }),
        interactive: false,
        keyboard: false,
      }).addTo(layer)
    }
    // Fit the full route geometry, not a single comfort slice: a short first
    // slice used to zoom the map to the slice's one point (zoom 19) and push
    // the rest of the route, the badge and the destination callout off-screen.
    // On mobile the 360px results sheet covers the bottom, so keep the route
    // (and its badge) in the visible map above it.
    const mobile = window.matchMedia('(max-width: 767px)').matches
    map.fitBounds(L.latLngBounds(coords), {
      paddingTopLeft: [24, 24],
      paddingBottomRight: [24, mobile ? 400 : 24],
    })
  }

  async function handleSaveRoute() {
    if (!route) return
    savedError = ''
    try {
      const saved = await saveRoute(route.name, {
        name: route.name,
        waypoints: route.waypoints,
        geometry: route.geometry,
        distance_m: route.distance_m,
        duration_s: route.duration_s,
        comfort_score: route.comfort_score,
        explanation: route.explanation,
        applied_preference: route.applied_preference,
        preference_source: route.preference_source,
        weather: {
          temperature: route.weather.temperature,
          cloudCover: route.weather.cloudCover ?? route.weather.cloud_cover ?? 0,
        },
        timestamp: route.timestamp,
        comfort_profile: route.comfort_profile,
      })
      savedRoutes = [saved, ...savedRoutes.filter((r) => r.id !== saved.id)]
    } catch (err) {
      savedError = err instanceof Error ? err.message : String(err)
    }
  }

  async function handleRecall(id: string) {
    savedError = ''
    try {
      const saved = await recallRoute(id)
      const snap = saved.snapshot
      route = {
        id: saved.id,
        name: saved.name,
        description: saved.description,
        waypoints: snap.waypoints,
        status: 'active',
        timestamp: snap.timestamp,
        comfort_score: snap.comfort_score,
        explanation: snap.explanation,
        geometry: snap.geometry,
        distance_m: snap.distance_m,
        duration_s: snap.duration_s,
        applied_preference: snap.applied_preference,
        preference_source: snap.preference_source,
        weather: snap.weather,
        comfort_profile: snap.comfort_profile,
      }
      start = ''
      end = ''
      drawRoute()
    } catch (err) {
      savedError = err instanceof Error ? err.message : String(err)
    }
  }

  async function handleDelete(id: string) {
    savedError = ''
    try {
      await deleteRoute(id)
      savedRoutes = savedRoutes.filter((r) => r.id !== id)
    } catch (err) {
      savedError = err instanceof Error ? err.message : String(err)
    }
  }

  /** Swap origin and destination (queries, selections, coords). */
  function swapEndpoints() {
    const startQuery = start
    start = end
    end = startQuery
    const startSel = startSuggestion
    startSuggestion = endSuggestion
    endSuggestion = startSel
    const startC = startCoords
    startCoords = endCoords
    endCoords = startC
  }

  async function togglePrefs() {
    showPrefs = !showPrefs
    if (showPrefs && !prefs) {
      prefsError = ''
      try {
        prefs = await getPrefs()
      } catch (err) {
        prefsError = err instanceof Error ? err.message : String(err)
      }
    }
  }

  async function handlePrefsSave() {
    if (!prefs) return
    prefsError = ''
    try {
      prefs = await updatePrefs(prefs)
    } catch (err) {
      prefsError = err instanceof Error ? err.message : String(err)
    }
  }

  // 041: the desktop comfort panel applies immediately (the design has no
  // Save button there). The local state drives the next /route request even
  // when the preferences API is unavailable (no database on the free stand).
  $: shadeLabel = shade === 'hot' ? 'More shade' : shade === 'cloudy' ? 'More sun' : 'Balanced'
  $: preferenceSummary = avoidTraffic ? `${shadeLabel} · Quieter streets` : shadeLabel
  $: preferenceBadge = avoidTraffic ? `${shadeLabel} · Quieter` : shadeLabel
  $: condition =
    (route?.weather.cloudCover ?? route?.weather.cloud_cover ?? 0) >= 70 ? 'Overcast' : 'Sunny'
  $: temperature = route?.weather ? Math.round(route.weather.temperature) : null
  $: areaLabel = (() => {
    const parts = start
      .split(',')
      .map((part) => part.trim())
      .filter(Boolean)
    return parts.length > 1 ? parts[parts.length - 1] : ''
  })()

  async function persistComfort() {
    if (!prefs) return
    prefsError = ''
    prefs = { ...prefs, default_preference: shade, avoid_traffic: avoidTraffic }
    try {
      prefs = await updatePrefs(prefs)
    } catch (err) {
      prefsError = err instanceof Error ? err.message : String(err)
    }
  }

  // 042 AC-1: a parked map pick is built by the builder's pill, so a
  // preference change must not fire /route behind its back.
  function replanIfReady() {
    if (awaitingBuild) return
    if (startCoords && endCoords) void planRoute()
  }

  // 042 AC-1/AC-2: the builder's pill is the only /route trigger while a
  // map-picked destination is parked. Building re-enables auto-plan, so the
  // resulting route opens the sheet with the 041 result card.
  async function handleBuildRoute() {
    if (!startCoords || !endCoords) return
    building = true
    error = ''
    awaitingBuild = false
    suppressAutoOpen = false
    drawerOpen = true
    // The build only succeeded when planRoute left no error behind; a failed
    // build re-parks the planner so only the pill retries it.
    try {
      await planRoute()
    } finally {
      building = false
      const failed = error !== ''
      awaitingBuild = failed
      suppressAutoOpen = failed
    }
  }

  function handleShade(event: CustomEvent<'hot' | 'cloudy' | 'balanced'>) {
    shade = event.detail
    shadeManual = true
    void persistComfort()
    replanIfReady()
  }

  function handleQuieter(event: CustomEvent<boolean>) {
    avoidTraffic = event.detail
    void persistComfort()
    replanIfReady()
  }

  // 041 T5: the mobile sheet stages its choices locally and commits them on
  // "Apply preferences" (save, close, re-plan) — unlike the desktop panel,
  // which applies each change immediately.
  function handleSheetShade(event: CustomEvent<'hot' | 'cloudy' | 'balanced'>) {
    shade = event.detail
    shadeManual = true
  }

  function handleSheetQuieter(event: CustomEvent<boolean>) {
    avoidTraffic = event.detail
  }

  function handlePrefsSheetApply() {
    showPrefsSheet = false
    void persistComfort()
    replanIfReady()
  }

  function handleComfortReset() {
    shade = 'balanced'
    shadeManual = true
    avoidTraffic = false
    void persistComfort()
    replanIfReady()
  }

  // The weather auto-rule's choice is what the design shows as active until
  // the walker makes an explicit choice; it is display state, not a save.
  $: if (route && route.preference_source === 'auto' && !shadeManual) {
    const applied = route.applied_preference
    shade =
      applied === 'hot' || applied === 'cloudy' || applied === 'balanced' ? applied : 'balanced'
  }
</script>

<svelte:head>
  <title>Comfort Walking Router</title>
</svelte:head>

<svelte:window on:keydown={onKeydown} />

<header data-testid="top-nav">
  <div class="nav-brand">
    <div class="nav-tile">
      <svg class="nav-tile-icon" viewBox="0 0 24 24" aria-hidden="true">
        <path d={materialPaths.directions_walk} fill="currentColor" />
      </svg>
    </div>
    <span class="nav-divider"></span>
    <span class="nav-tagline">A nicer way to get there.</span>
  </div>

  <nav class="nav-center" aria-label="Primary">
    <button type="button" class="nav-link primary">Plan a walk</button>
    <button
      type="button"
      class="nav-link secondary"
      data-testid="saved-walks"
      on:click={() => (showSavedWalks = true)}
    >
      Saved walks
    </button>
  </nav>

  <div class="nav-right">
    <button
      type="button"
      class="nav-how"
      data-testid="how-it-works"
      on:click={() => (showHowItWorks = true)}
    >
      <span>How it works</span>
      <span class="nav-chevron" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
          <path d="M7.41 8.59 12 13.17l4.59-4.58L18 10l-6 6-6-6z" />
        </svg>
      </span>
    </button>
    {#if route?.weather && temperature !== null}
      <span class="nav-weather" data-testid="weather-chip">
        {areaLabel ? `${areaLabel} · ` : ''}{condition}, {temperature}°C
      </span>
    {/if}
  </div>

  <span data-testid="brand-name" class="brand-name sr-only">Comfort Walking Router</span>
</header>

<main>
  <div id="map" data-testid="map" bind:this={mapElement}></div>

  <div class="map-controls">
    <button
      type="button"
      class="map-control"
      data-testid="map-locate"
      aria-label="Centre on my location"
      on:click={retryLocate}
    >
      <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M21 3 3 10.53v.98l6.84 2.65L12.48 21h.98L21 3z" />
      </svg>
    </button>
    <div class="zoom-group" role="group" aria-label="Map zoom">
      <button
        type="button"
        class="map-control zoom"
        data-testid="map-zoom-in"
        aria-label="Zoom in"
        on:click={() => map?.zoomIn()}
      >
        +
      </button>
      <button
        type="button"
        class="map-control zoom"
        data-testid="map-zoom-out"
        aria-label="Zoom out"
        on:click={() => map?.zoomOut()}
      >
        −
      </button>
    </div>
  </div>

  {#if !isDesktop && route?.weather && temperature !== null}
    <span class="mobile-weather" data-testid="mobile-weather">
      <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path
          d="M6.76 4.84l-1.8-1.79-1.41 1.41 1.79 1.79 1.42-1.41zM4 10.5H1v2h3v-2zm9-9.95h-2V3.5h2V.55zm7.45 3.91l-1.41-1.41-1.79 1.79 1.41 1.41 1.79-1.79zm-3.21 13.7l1.79 1.8 1.41-1.41-1.8-1.79-1.4 1.4zM20 10.5v2h3v-2h-3zm-8-5c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6-2.69-6-6-6zm-1 16.95h2V19.5h-2v2.95zm-7.45-3.91l1.41 1.41 1.79-1.8-1.41-1.41-1.79 1.8z"
        />
      </svg>
      {condition} · {temperature}°
    </span>
  {/if}

  {#if currentStep === 'plan' && !isDesktop}
    <TopSearchCard
      extraClass="top-card"
      bind:startQuery={start}
      bind:endQuery={end}
      bind:startSelected={startSuggestion}
      bind:endSelected={endSuggestion}
      {activePick}
      on:pick={(e) => beginPick(e.detail)}
      on:swap={swapEndpoints}
    />
  {/if}

  <aside
    id="desktop-sidebar"
    class="overlay-panel"
    class:collapsed={sidebarCollapsed}
    data-testid="sidebar"
  >
    {#if isDesktop && currentStep === 'plan'}
      <div class="sidebar-search-wrap">
        <TopSearchCard
          extraClass="sidebar-search"
          bind:startQuery={start}
          bind:endQuery={end}
          bind:startSelected={startSuggestion}
          bind:endSelected={endSuggestion}
          {activePick}
          on:pick={(e) => beginPick(e.detail)}
          on:swap={swapEndpoints}
        />
      </div>
    {/if}

    {#if isDesktop}
      <ComfortPanel
        preference={shade}
        {avoidTraffic}
        weather={route?.weather
          ? {
              temperature: route.weather.temperature,
              cloudCover: route.weather.cloudCover ?? route.weather.cloud_cover ?? 50,
            }
          : null}
        on:shade={handleShade}
        on:quieter={handleQuieter}
        on:reset={handleComfortReset}
      />
    {/if}

    {#if locateError}
      <div class="locate-notice" role="alert">
        {locateError}
        <button type="button" class="locate-retry" on:click={retryLocate}> Use my location </button>
      </div>
    {/if}
    {#if activePick}
      <p class="pick-hint" role="status">
        {pickHint(activePick)}{pickBusy ? ' (locating…)' : ' — Esc to cancel'}
      </p>
    {/if}
    {#if pickError}
      <p class="error" role="alert">{pickError}</p>
    {/if}
    {#if prefsError}
      <p class="error" role="alert">{prefsError}</p>
    {/if}
    {#if error}
      <p class="error">{error}</p>
    {/if}

    {#if isDesktop}
      {#if route}
        <section class="walk-choice" aria-labelledby="choose-walk-title">
          <div class="choice-heading">
            <h2 id="choose-walk-title">Choose your walk</h2>
            <span class="route-count">1 route</span>
          </div>
          <RouteCard
            {route}
            profile={route.comfort_profile ?? []}
            {avoidTraffic}
            {suggestionAttribution}
          />
          <div class="cta-row">
            {#if $walkMode.active || $walkMode.arrived}
              <WalkControls route={walkRoute} profile={route.comfort_profile ?? []} />
            {:else}
              <button
                type="button"
                class="walk-start"
                data-testid="start-walk"
                aria-label="Start walk mode"
                on:click={() => startWalk(walkRoute, route?.comfort_profile ?? [])}
              >
                <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d={materialPaths.arrow_upward} />
                </svg>
                <span>Start walk</span>
              </button>
            {/if}
            <button
              type="button"
              class="save-route"
              data-testid="save-route"
              aria-label="Save route"
              on:click={handleSaveRoute}
            >
              <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path
                  d="M17 3H7c-1.1 0-1.99.9-1.99 2L5 21l7-3 7 3V5c0-1.1-.9-2-2-2zm0 15l-5-2.18L7 18V5h10v13z"
                />
              </svg>
            </button>
          </div>
        </section>
      {:else}
        <p class="empty">Plan a route to see your walk.</p>
        <div class="cta-row">
          <button
            type="button"
            class="walk-start"
            data-testid="start-walk"
            aria-label="Start walk mode"
            disabled
          >
            <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d={materialPaths.arrow_upward} />
            </svg>
            <span>Start walk</span>
          </button>
          <button
            type="button"
            class="save-route"
            data-testid="save-route"
            aria-label="Save route"
            disabled
          >
            <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path
                d="M17 3H7c-1.1 0-1.99.9-1.99 2L5 21l7-3 7 3V5c0-1.1-.9-2-2-2zm0 15l-5-2.18L7 18V5h10v13z"
              />
            </svg>
          </button>
        </div>
      {/if}
    {/if}

    <section class="walk">
      {#if arrival?.arrived && !arrivalDismissed}
        <ArrivalCard
          distanceMeters={arrival.distanceMeters}
          durationMinutes={route ? route.duration_s / 60 : 0}
          comfortScore={route ? route.comfort_score : 0}
          topFactors={route ? route.explanation.slice(0, 3) : []}
          onDismiss={dismissArrival}
          onPlanAnother={planAnotherWalk}
        />
      {/if}
    </section>
  </aside>

  <ul
    class="map-legend comfort-legend"
    data-testid="comfort-legend"
    aria-label="Comfort band legend"
  >
    <li class="legend-route">
      <span class="legend-swatch" style="background:{bandColour('good')}"></span>
      Your comfort route
    </li>
    {#each COMFORT_BANDS as band (band.band)}
      <li class="comfort-band comfort-band--{band.band}">
        <span class="legend-swatch" style="background:{band.colour}"></span>
        {band.band} · {band.range}/100
      </li>
    {/each}
  </ul>

  <!-- Mobile results sheet ("Your kind of walk", 041 T4): the shared card
       and CTA live inside the sheet; the desktop sidebar never renders it. -->
  {#if !isDesktop}
    <BottomDrawer
      bind:open={drawerOpen}
      {route}
      segments={route?.comfort_profile ?? []}
      {avoidTraffic}
      {suggestionAttribution}
      {preferenceSummary}
      {suppressAutoOpen}
      {error}
      canBuild={endCoords !== null}
      {building}
      on:edit={() => (showPrefsSheet = true)}
      on:build={handleBuildRoute}
      on:start={() => startWalk(walkRoute, route?.comfort_profile ?? [])}
      on:save={handleSaveRoute}
      on:saved={() => (showSavedWalks = true)}
    />

    <!-- 041 T5 (AC-3/AC-4): the mobile "Walk your way" comfort sheet, opened
         from the results sheet's Edit. It stages shade/quieter locally; the
         footer's "Apply preferences" saves, closes and re-plans. -->
    <PreferencesSheet
      bind:open={showPrefsSheet}
      preference={shade}
      {avoidTraffic}
      weather={route
        ? {
            temperature: route.weather.temperature,
            cloudCover: route.weather.cloudCover ?? route.weather.cloud_cover ?? 0,
          }
        : null}
      on:close={() => (showPrefsSheet = false)}
      on:shade={handleSheetShade}
      on:quieter={handleSheetQuieter}
      on:apply={handlePrefsSheetApply}
    />
  {/if}

  <!-- Google-Maps-style edge handle: a vertical pill centred on the panel's
       inner edge. Rendered as a sibling of <aside> inside <main> so it is
       never clipped by the aside's `overflow-y: auto` and stays reachable
       when the collapsed panel is translated off-screen. -->
  <button
    type="button"
    class="sidebar-handle"
    data-testid="sidebar-handle"
    class:collapsed={sidebarCollapsed}
    aria-controls="desktop-sidebar"
    aria-expanded={!sidebarCollapsed}
    aria-label={sidebarCollapsed ? 'Show controls' : 'Hide controls'}
    on:click={() => (sidebarCollapsed = !sidebarCollapsed)}
  >
    <span class="sidebar-handle-chevron" aria-hidden="true">
      {sidebarCollapsed ? '‹' : '›'}
    </span>
  </button>

  <!-- AC-5: when start geolocation is unavailable/denied with no fix, ask for
       the origin via the StartLocationModal overlay. Rendered as a sibling of
       the other <main> overlays (aside, BottomDrawer, sidebar-handle) so it
       floats above the map and never blocks the page; it closes when a typed
       suggestion or a map pick chooses the origin. -->
  {#if startModalOpen}
    <StartLocationModal
      bind:open={startModalOpen}
      on:chosen={(e) => handleStartChosen(e.detail)}
      on:pick={handleStartPick}
      on:close={handleStartModalClose}
    />
  {/if}

  {#if showSavedWalks}
    <div class="dialog-scrim" role="presentation" on:click|self={() => (showSavedWalks = false)}>
      <section
        class="app-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="saved-walks-title"
        data-testid="saved-walks-dialog"
      >
        <header class="dialog-head">
          <h2 id="saved-walks-title">Saved walks</h2>
          <button
            type="button"
            class="dialog-close"
            aria-label="Close saved walks"
            on:click={() => (showSavedWalks = false)}
          >
            ×
          </button>
        </header>
        {#if savedError}
          <p class="error" role="alert">{savedError}</p>
        {/if}
        {#if savedRoutes.length === 0}
          <p class="empty">No saved walks yet.</p>
        {:else}
          <ul class="dialog-list">
            {#each savedRoutes as saved (saved.id)}
              <li>
                <span class="saved-name">{saved.name}</span>
                <span class="dialog-actions">
                  <button
                    type="button"
                    on:click={() => {
                      handleRecall(saved.id)
                      showSavedWalks = false
                    }}>Recall</button
                  >
                  <button type="button" on:click={() => handleDelete(saved.id)}>Delete</button>
                </span>
              </li>
            {/each}
          </ul>
        {/if}
      </section>
    </div>
  {/if}

  {#if showHowItWorks}
    <div class="dialog-scrim" role="presentation" on:click|self={() => (showHowItWorks = false)}>
      <section
        class="app-dialog how-it-works"
        role="dialog"
        aria-modal="true"
        aria-labelledby="how-it-works-title"
        data-testid="how-it-works-dialog"
      >
        <header class="dialog-head">
          <h2 id="how-it-works-title">How comfort works</h2>
          <button
            type="button"
            class="dialog-close"
            aria-label="Close how it works"
            on:click={() => (showHowItWorks = false)}
          >
            ×
          </button>
        </header>
        <p>
          A walk's comfort score blends shade, quiet and the weather along the route. More shade,
          quieter streets and pleasant temperatures score higher.
        </p>
        <p>
          The profile shows the score in short bands. Your sun &amp; shade and quieter-street
          preferences re-weight the same data; they never change the route geometry.
        </p>
        <p>
          The fastest route is not a second option here: the API returns one route, so the card
          shows the comfort route and its honest metrics.
        </p>
      </section>
    </div>
  {/if}
</main>

<style>
  :global(html),
  :global(body) {
    margin: 0;
    height: 100%;
  }

  main {
    position: relative;
    height: 100vh;
    width: 100vw;
    overflow: hidden;
  }

  /* AC-1: the map is full-bleed behind every overlay (sidebar, drawer, cards),
     so the desktop sidebar overlays it instead of shrinking it. Leaflet needs
     an explicit size, hence the absolute inset-0 sizing. */
  #map {
    position: absolute;
    inset: 0;
  }

  /* Desktop sidebar: floating overlay above the map. Single breakpoint source
     of truth: 768px. The drawer below uses `not (min-width: 768px)` so both
     rules derive from the same value and can never drift apart. */
  aside {
    display: none;
    position: absolute;
    /* Sits directly beneath the 72px desktop top nav; the map stays
       full-bleed behind both, so nothing reflows at 1280x800. */
    top: 72px;
    left: 0;
    bottom: 0;
    width: 380px;
    padding: 20px;
    overflow-y: auto;
    background: var(--cwr-surface, #fff);
    z-index: 1000;
    box-shadow: 2px 0 8px rgba(0, 0, 0, 0.15);
  }

  /* The Google-Maps-style edge handle is a desktop-only surface. It must be
     hidden by default so that below 768px (where the mobile bottom drawer owns
     the controls) it never renders as a static in-flow button over the map. */
  .sidebar-handle {
    display: none;
  }

  @media (min-width: 768px) {
    aside {
      display: block;
      transition: transform 0.25s ease;
    }

    /* T11: hide the mobile <BottomDrawer /> on desktop so the sidebar and
       drawer are never visible together. :global() is required because the
       .bottom-drawer class is scoped inside BottomDrawer.svelte. */
    :global(.bottom-drawer) {
      display: none;
    }

    /* T10 step 6: these collapse/toggle rules are scoped to this
       min-width: 768px block only; mobile rendering is owned entirely by
       the <BottomDrawer /> component's own styles. */
    /* T17 step 1: Google-Maps-style edge handle replaces the old
       `.sidebar-toggle` button. A vertical pill centred on the panel's inner
       edge, absolutely positioned as a sibling of <aside> inside <main> so it
       is never clipped by the aside's `overflow-y: auto` and stays reachable
       even when the panel is translated off-screen by `aside.collapsed`.
       Scoped to this min-width: 768px block so the mobile drawer's
       `.drawer-toggle` CSS is untouched. */
    .sidebar-handle {
      position: absolute;
      top: 50%;
      /* Straddle the sidebar's inner (left) edge: the aside is anchored at
         right: 0 with width min(360px, 90vw), so its inner edge sits that far
         from the viewport's right; the pill is centred on it. As a sibling of
         <aside> inside <main>, it never moves when the panel collapses and
         stays reachable in both states. */
      left: calc(380px - 0.625rem);
      transform: translateY(-50%);
      width: 1.25rem;
      height: 3rem;
      padding: 0;
      border: 1px solid #ddd;
      border-radius: 0.625rem;
      background: #fff;
      box-shadow: 0 1px 4px rgb(0 0 0 / 0.2);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 1001;
      cursor: pointer;
    }

    .sidebar-handle:hover {
      background: #f1f3f4;
      box-shadow: 0 1px 6px rgb(0 0 0 / 0.3);
    }

    /* T17 step 3: when the panel collapses, the handle must stay fully
       on-screen and clickable. The aside slides out to the right, so the
       handle slides with the panel's inner edge to the viewport's right
       edge: half the pill (0.625rem) remains visible at right: 0. */
    .sidebar-handle.collapsed {
      left: -0.625rem;
    }

    .sidebar-handle-chevron {
      font-size: 0.9rem;
      line-height: 1;
      color: #5f6368;
      user-select: none;
    }

    /* T10 step 4 / T17 step 3: slide the collapsed sidebar fully off-screen
       (right edge), with the transition above animating restore back into
       view. Translated past 100% by the shadow blur (8px) so no shadow edge
       peeks back on-screen. The `.sidebar-handle` is a sibling of <aside>
       inside <main>, so this transform never moves it: it stays fully
       on-screen and clickable at right: 0 in both collapsed and expanded
       states. */
    aside.collapsed {
      transform: translateX(calc(-100% - 8px));
    }
  }

  .hint {
    font-size: 0.85rem;
    color: #555;
    margin: 0 0 0.5rem;
  }

  h1 {
    font-size: 1.2rem;
    margin-top: 0;
  }

  label {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    font-size: 0.85rem;
    font-weight: 600;
  }

  input,
  select,
  button {
    font: inherit;
    padding: 0.5rem;
  }

  button {
    cursor: pointer;
  }

  button:disabled {
    cursor: wait;
    opacity: 0.6;
  }

  .error {
    color: #b00020;
  }

  .saved-routes {
    margin-top: 1.5rem;
  }

  .saved-list {
    list-style: none;
    margin: 0.5rem 0 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .saved-list li {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.5rem;
  }

  .saved-name {
    font-size: 0.9rem;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .saved-actions {
    display: flex;
    gap: 0.25rem;
  }

  .empty {
    font-size: 0.85rem;
    color: #666;
  }

  .chip {
    display: inline-block;
    padding: 0.25rem 0.5rem;
    background: #eef;
    border-radius: 4px;
    font-size: 0.8rem;
    margin-top: 0.5rem;
  }

  .stats {
    font-weight: 600;
  }

  .score {
    font-size: 1.1rem;
    font-weight: 700;
    color: #1a7f37;
  }

  .factors {
    margin: 0.5rem 0 0;
    padding-left: 1.25rem;
    font-size: 0.85rem;
    color: #444;
  }

  #map {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    z-index: 0;
  }

  button {
    cursor: pointer;
  }

  button:disabled {
    cursor: wait;
    opacity: 0.6;
  }

  .error {
    color: #b00020;
  }

  .saved-routes {
    margin-top: 1.5rem;
  }

  .saved-list {
    list-style: none;
    margin: 0.5rem 0 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .saved-list li {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.5rem;
  }

  .saved-name {
    font-size: 0.9rem;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .saved-actions {
    display: flex;
    gap: 0.25rem;
  }

  .empty {
    font-size: 0.85rem;
    color: #666;
  }

  .chip {
    display: inline-block;
    padding: 0.25rem 0.5rem;
    background: #eef;
    border-radius: 4px;
    font-size: 0.8rem;
    margin-top: 0.5rem;
  }

  .stats {
    font-weight: 600;
  }

  .score {
    font-size: 1.1rem;
    font-weight: 700;
    color: #1a7f37;
  }

  .factors {
    margin: 0.5rem 0 0;
    padding-left: 1.25rem;
    font-size: 0.85rem;
    color: #444;
  }

  /* 014 T6: the picker toggles this class on the Leaflet container at runtime.
     `:global` keeps Svelte from pruning a selector it cannot see in markup. */
  :global(#map.crosshair) {
    cursor: crosshair;
  }

  .locate-notice {
    position: absolute;
    top: 0.75rem;
    left: 50%;
    transform: translateX(-50%);
    z-index: 1000;
    max-width: 90%;
    padding: 0.5rem 0.9rem;
    background: #fff8e1;
    border: 1px solid #e0c36a;
    border-radius: 6px;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
    font-size: 0.85rem;
    color: #5c4a00;
    pointer-events: none;
  }

  .locate-retry {
    pointer-events: auto;
    margin-left: 0.5rem;
    padding: 0.15rem 0.6rem;
    background: #5c4a00;
    color: #fff8e1;
    border: none;
    border-radius: 4px;
    font-size: 0.8rem;
    cursor: pointer;
  }

  .locate-retry:hover {
    background: #7a6300;
  }

  /* 028 T4: comfort profile legend and segment list */
  .comfort-legend,
  .comfort-segments {
    list-style: none;
    margin: 0.5rem 0 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem 0.75rem;
    font-size: 0.8rem;
  }
  /* 041 T1: desktop-only top nav. Hidden below 768px so the mobile layout
     (full-bleed map + bottom drawer) stays exactly as it was. */
  header[data-testid='top-nav'] {
    display: none;
  }

  .nav-brand {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .nav-tile {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    border-radius: 8px;
    background: var(--cwr-brand);
  }

  .nav-tile-icon {
    width: 24px;
    height: 24px;
    color: #ffffff;
  }

  .nav-divider {
    width: 1px;
    height: 28px;
    background: var(--cwr-line-strong);
  }

  .nav-tagline {
    font-size: 13px;
    font-weight: 400;
    color: #7b887f;
  }

  .nav-center {
    position: absolute;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .nav-link {
    padding: 8px 14px;
    border: none;
    border-radius: 999px;
    background: transparent;
    cursor: pointer;
  }

  .nav-link.primary {
    font-size: 14px;
    font-weight: 600;
    color: var(--cwr-brand);
  }

  .nav-link.secondary {
    font-size: 14px;
    font-weight: 500;
    color: #728077;
  }

  .nav-right {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-left: auto;
  }

  .nav-how {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 6px 8px;
    border: none;
    background: transparent;
    font-size: 13px;
    font-weight: 500;
    color: var(--cwr-muted);
    cursor: pointer;
  }

  .nav-chevron {
    display: inline-flex;
    align-items: center;
  }

  .nav-weather {
    display: inline-flex;
    align-items: center;
    padding: 6px 12px;
    border-radius: 999px;
    background: var(--cwr-sun-bg);
    color: var(--cwr-sun-ink);
    font-size: 13px;
    box-shadow: var(--cwr-shadow-pill);
  }

  /* The router name stays in the DOM for tests and screen readers. */
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }

  /* 041: the endpoint card lives inside the 380px panel on desktop; the
     component is absolutely positioned for the mobile map, so place it in a
     relative wrapper and reset the inset. */
  .sidebar-search-wrap {
    position: relative;
    width: 100%;
    margin-bottom: 14px;
  }

  :global(.top-card) {
    padding: 5px !important;
    gap: 2px !important;
    border-radius: 18px !important;
  }

  .sidebar-search-wrap :global(.top-search-card) {
    position: relative;
    inset: auto;
    width: 100%;
    min-height: 108px;
    padding: 8px;
    border: 1px solid var(--cwr-line);
    border-radius: 12px;
    box-shadow: none;
  }

  .walk-choice {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 10px;
  }

  .choice-heading {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
  }

  .choice-heading h2 {
    margin: 0;
    color: var(--cwr-ink);
    font-size: 16px;
    font-weight: 600;
  }

  .route-count {
    color: var(--cwr-muted-2);
    font-size: 11px;
  }

  .cta-row {
    position: sticky;
    bottom: 0;
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: auto;
    padding: 12px 0 4px;
    background: var(--cwr-surface);
  }

  .cta-row :global(.walk-controls) {
    flex: 1;
    flex-wrap: wrap;
  }

  .walk-start {
    display: inline-flex;
    flex: 1;
    align-items: center;
    justify-content: center;
    gap: 8px;
    height: 48px;
    border: none;
    border-radius: 999px;
    background: var(--cwr-brand);
    color: #ffffff;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
  }

  .walk-start svg {
    width: 20px;
    height: 20px;
  }

  .save-route {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    border: 1px solid var(--cwr-line-strong);
    border-radius: 12px;
    background: var(--cwr-surface);
    color: var(--cwr-ink);
    cursor: pointer;
  }

  .save-route svg {
    width: 20px;
    height: 20px;
  }

  .saved-walks {
    margin-top: 12px;
    color: var(--cwr-muted);
    font-size: 12px;
  }

  .saved-walks summary {
    cursor: pointer;
  }

  .saved-list {
    list-style: none;
    margin: 8px 0 0;
    padding: 0;
  }

  .saved-list li {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    padding: 4px 0;
  }

  .saved-actions {
    display: flex;
    gap: 4px;
  }

  /* The legend floats over the map, 24px right of the panel. */
  .map-legend {
    display: none;
  }

  @media (min-width: 768px) {
    .map-legend {
      position: absolute;
      left: 404px;
      bottom: 21px;
      z-index: 900;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 4px 12px;
      max-width: 340px;
      margin: 0;
      padding: 10px 14px;
      list-style: none;
      border-radius: 10px;
      background: var(--cwr-surface);
      box-shadow: var(--cwr-shadow-pill);
      color: var(--cwr-muted);
      font-size: 11px;
    }

    .map-legend .comfort-band {
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
  }

  .legend-swatch {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 999px;
  }

  /* 041 T6: custom map controls replace Leaflet's default zoom; the locate
     button uses the same map.locate path as the sidebar retry. */
  :global(.leaflet-control-zoom) {
    display: none;
  }

  .map-controls {
    position: absolute;
    right: 24px;
    bottom: 24px;
    /* Below the 60-level dialog scrim so an open preferences sheet covers
       the locate button instead of letting it float over the text. */
    z-index: 50;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .map-control {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    padding: 0;
    border: 1px solid var(--cwr-line);
    border-radius: 12px;
    background: var(--cwr-surface);
    color: var(--cwr-ink);
    cursor: pointer;
  }

  .map-control svg {
    width: 20px;
    height: 20px;
  }

  .zoom-group {
    display: flex;
    flex-direction: column;
    overflow: hidden;
    border: 1px solid var(--cwr-line);
    border-radius: 12px;
    background: var(--cwr-surface);
  }

  .zoom-group .zoom {
    border: none;
    border-radius: 0;
    font-size: 20px;
    line-height: 1;
  }

  .zoom-group .zoom + .zoom {
    border-top: 1px solid var(--cwr-line);
  }

  .mobile-weather {
    display: none;
  }

  @media (max-width: 767px) {
    .map-controls {
      right: 16px;
      bottom: 380px;
    }

    .zoom-group {
      display: none;
    }

    .mobile-weather {
      position: absolute;
      top: 121px;
      left: 16px;
      z-index: 900;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      height: 32px;
      padding: 0 12px;
      border-radius: 99px;
      background: var(--cwr-sun-bg);
      color: var(--cwr-sun-ink);
      font-size: 12px;
      font-weight: 500;
    }

    .mobile-weather svg {
      width: 16px;
      height: 16px;
    }
  }

  /* Leaflet divIcon route badge: one route, duration + active preference. */
  :global(.route-badge) {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 10px 14px;
    border-radius: 12px;
    background: var(--cwr-brand);
    color: #ffffff;
    box-shadow: var(--cwr-shadow-card);
    white-space: nowrap;
  }

  :global(.route-badge-duration) {
    font-size: 21px;
    font-weight: 600;
    line-height: 1.1;
  }

  :global(.route-badge-sub) {
    font-size: 12px;
    font-weight: 500;
    color: var(--cwr-brand-soft);
  }

  :global(.route-badge-icon) {
    border: none;
    background: transparent;
  }

  :global(.dest-callout) {
    padding: 6px 10px;
    border: none;
    border-radius: 10px;
    background: var(--cwr-surface);
    color: var(--cwr-ink);
    box-shadow: var(--cwr-shadow-card);
    font-size: 12px;
    font-weight: 600;
  }

  .dialog-scrim {
    position: fixed;
    inset: 0;
    z-index: 1200;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
    background: rgb(23 43 36 / 0.35);
  }

  .app-dialog {
    width: min(420px, 100%);
    max-height: 80vh;
    overflow: auto;
    padding: 20px;
    border-radius: 18px;
    background: var(--cwr-surface);
    color: var(--cwr-ink);
    box-shadow: var(--cwr-shadow-card);
  }

  .dialog-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 12px;
  }

  .dialog-head h2 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
  }

  .dialog-close {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 34px;
    height: 34px;
    border: none;
    border-radius: 50%;
    background: var(--cwr-control-bg);
    color: var(--cwr-ink);
    font-size: 20px;
    line-height: 1;
    cursor: pointer;
  }

  .dialog-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .dialog-list li {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 8px 0;
    border-bottom: 1px solid var(--cwr-line);
  }

  .dialog-actions {
    display: flex;
    gap: 6px;
  }

  .how-it-works p {
    margin: 0 0 10px;
    color: var(--cwr-muted);
    font-size: 13px;
    line-height: 1.5;
  }

  :global(button:focus-visible),
  :global(a:focus-visible),
  :global(input:focus-visible) {
    outline: 2px solid var(--cwr-brand);
    outline-offset: 2px;
  }

  @media (prefers-reduced-motion: reduce) {
    :global(*) {
      animation: none !important;
      transition: none !important;
    }
  }

  @media (min-width: 768px) {
    header[data-testid='top-nav'] {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      display: flex;
      align-items: center;
      gap: 16px;
      height: 72px;
      padding: 0 24px;
      background: var(--cwr-surface);
      border-bottom: 1px solid var(--cwr-line);
      z-index: 1100;
    }
  }
</style>
