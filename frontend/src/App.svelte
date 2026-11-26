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
    cloudCover: number
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
  import { checkArrival } from './lib/navigation/arrival'
  import type { ArrivalSample, ArrivalStatus } from './lib/navigation/arrival'
  import type { LatLng } from './lib/navigation/interpolate'
  import { clearRerouteWarning, flagOffRoute, onFix, walkMode } from './lib/walkMode'
  import { DRIFT_DISTANCE_THRESHOLD_M, distanceToRouteMeters } from './lib/navigation/drift'
  import ArrivalCard from './lib/components/ArrivalCard.svelte'
  import Attribution from './lib/components/Attribution.svelte'
  import TopSearchCard from './lib/components/TopSearchCard.svelte'
  import BottomDrawer from './lib/components/BottomDrawer.svelte'
  import ControlsContent from './lib/components/ControlsContent.svelte'
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
          // 004 AC-3: a saved preference is the manual override. Omit it when
          // unset so the backend's weather auto-rule still decides.
          ...(prefs?.default_preference ? { preference: prefs.default_preference } : {}),
          prefer_lit: prefs?.prefer_lit ?? false,
          avoid_traffic: prefs?.avoid_traffic ?? false,
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
    if (currentMarker) {
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
    if (e.key === 'Escape' && activePick) {
      e.preventDefault()
      cancelPick()
    }
  }

  async function onMapClick(e: L.LeafletMouseEvent) {
    if (!activePick) return
    pickBusy = true
    try {
      const label = await reverseLabel(e.latlng.lat, e.latlng.lng)
      const coords: [number, number] = [e.latlng.lat, e.latlng.lng]
      if (activePick === 'start') {
        // A map-picked origin is manual: settle the geolocation pre-fill so a
        // later fix (or the in-flight first-fix geocode) never overwrites it.
        originPrefilled = true
        start = label
        setStartCoords(coords)
      } else {
        end = label
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
    let line: L.Polyline
    if (runs.length) {
      const lines: L.Polyline[] = []
      for (const run of runs) {
        const slice: [number, number][] = []
        coords.forEach((c, i) => {
          if (dists[i] >= run.from_m && dists[i] <= run.to_m) slice.push(c)
        })
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
        .bindTooltip('End')
        .addTo(layer)
    }
    map.fitBounds(line.getBounds(), { padding: [24, 24] })
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
        weather: route.weather,
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
</script>

<svelte:head>
  <title>Comfort Walking Router</title>
</svelte:head>

<svelte:window on:keydown={onKeydown} />

<main>
  <div id="map" data-testid="map" bind:this={mapElement}></div>

  {#if currentStep === 'plan'}
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
    <h1>Comfort Walking Router</h1>

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

    {#if error}
      <p class="error">{error}</p>
    {/if}

    {#if isDesktop}
      <ControlsContent
        {route}
        {walkRoute}
        profile={route?.comfort_profile ?? []}
        {prefs}
        {showPrefs}
        {savedRoutes}
        {savedError}
        {prefsError}
        {error}
        {suggestionAttribution}
        onTogglePrefs={togglePrefs}
        onPrefsSave={() => handlePrefsSave()}
        onSaveRoute={handleSaveRoute}
        onRecall={handleRecall}
        onDelete={handleDelete}
      />
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

  <!-- Mobile bottom drawer: same controls as the desktop sidebar, shown only
       below 768px so the sidebar and drawer are never visible together. -->
  <BottomDrawer>
    {#if !isDesktop}
      <ControlsContent
        {route}
        {walkRoute}
        profile={route?.comfort_profile ?? []}
        {prefs}
        {showPrefs}
        {savedRoutes}
        {savedError}
        {prefsError}
        {error}
        {suggestionAttribution}
        onTogglePrefs={togglePrefs}
        onPrefsSave={() => handlePrefsSave()}
        onSaveRoute={handleSaveRoute}
        onRecall={handleRecall}
        onDelete={handleDelete}
      />
    {/if}
  </BottomDrawer>

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
</main>

<style>
  :global(html),
  :global(body) {
    margin: 0;
    height: 100%;
    font-family:
      system-ui,
      -apple-system,
      sans-serif;
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
    top: 0;
    right: 0;
    bottom: 0;
    width: min(360px, 90vw);
    padding: 1rem;
    overflow-y: auto;
    background: #fff;
    z-index: 1000;
    box-shadow: -2px 0 8px rgba(0, 0, 0, 0.15);
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
      right: calc(min(360px, 90vw) - 0.625rem);
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
      right: -0.625rem;
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
      transform: translateX(calc(100% + 8px));
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
</style>
