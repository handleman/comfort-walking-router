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

  import { onDestroy, onMount } from 'svelte'
  import L from 'leaflet'
  import { personIcon, startPinIcon, endPinIcon } from './lib/map/icons'
  import { checkArrival } from './lib/navigation/arrival'
  import type { ArrivalSample, ArrivalStatus } from './lib/navigation/arrival'
  import type { LatLng } from './lib/navigation/interpolate'
  import WalkControls from './lib/WalkControls.svelte'
  import Step from './lib/components/Step.svelte'
  import { clearRerouteWarning, flagOffRoute, onFix, walkMode } from './lib/walkMode'
  import { DRIFT_DISTANCE_THRESHOLD_M, distanceToRouteMeters } from './lib/navigation/drift'
  import ArrivalCard from './lib/components/ArrivalCard.svelte'
  import Attribution from './lib/components/Attribution.svelte'
  import TopSearchCard from './lib/components/TopSearchCard.svelte'
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

  let currentStep: 'plan' | 'review' | 'walk' = 'plan'
  let mapElement: HTMLDivElement
  let map: L.Map | null = null
  let activePick: PickRole | null = null
  let pickBusy = false
  let pickError = ''
  let routeLayer: L.LayerGroup | null = null

  let start = ''
  let end = ''
  let preference = ''
  let route: Route | null = null
  let suggestionAttribution = ''
  let error = ''
  let loading = false
  let manualOverride = false
  let savedRoutes: SavedRoute[] = []
  let prefs: Prefs | null = null
  let showPrefs = false
  let savedError = ''
  let prefsError = ''
  let locateError = ''
  let didCenterOnUser = false
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

  let arrival: ArrivalStatus | null = null
  let arrivalDismissed = false
  let drawerOpen = false

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
    map = L.map(mapElement).setView([48.137, 11.575], 12)
    // Full-bleed map: re-measure whenever the viewport or overlay panel
    // changes the container's size (Leaflet caches the initial dimensions).
    const resizeObserver = new ResizeObserver(() => {
      map?.invalidateSize()
    })
    resizeObserver.observe(mapElement)
    onDestroy(() => resizeObserver.disconnect())
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map)
    ensureToken()
    // Continuous position fixes (spec 007, T10): watch geolocation from page
    // load so every fix fires `locationfound`, feeding onFix, the drift check,
    // and arrival detection for the whole walk, not just the first fix.
    map.locate({ watch: true, setView: false, maxZoom: 16, enableHighAccuracy: true })
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
      unsubscribeWalkMode()
      map?.stopLocate()
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

  function onLocationFound(e: L.LocationEvent) {
    locateError = ''
    if (!map) return
    const { lat, lng } = e.latlng
    // Center once on the first fix, then keep the view where the user put it
    // (the watch must not yank the map around while they browse a route).
    if (!didCenterOnUser) {
      didCenterOnUser = true
      map.setView([lat, lng], 16)
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

  // The last request that produced the route on screen, so an identical repeat
  // renders the cached result instead of a second external call (005 AC-3).
  let lastQuery = ''

  async function submitRoute() {
    error = ''
    const appliedPreference = manualOverride
      ? preference || null
      : prefs?.default_preference || null
    const query = JSON.stringify([start, end, appliedPreference, startCoords, endCoords])
    if (route && query === lastQuery) return
    loading = true
    try {
      const response = await fetch('/route', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          start,
          end,
          preference: appliedPreference,
          prefer_lit: prefs?.prefer_lit ?? false,
          avoid_traffic: prefs?.avoid_traffic ?? false,
          ...(startCoords ? { start_coords: startCoords } : {}),
          ...(endCoords ? { end_coords: endCoords } : {}),
        }),
      })
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.message || data.detail || `Route request failed (${response.status})`)
      }
      route = data
      currentStep = 'review'
      lastQuery = query
      suggestionAttribution = data.attribution ?? suggestionAttribution
      drawRoute()
    } catch (err) {
      route = null
      suggestionAttribution = ''
      error = err instanceof Error ? err.message : String(err)
    } finally {
      loading = false
    }
  }

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
  <div id="map" bind:this={mapElement}></div>

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
      on:more={() => (showPrefs = !showPrefs)}
    />
  {/if}

  <aside class="overlay-panel">
    <h1>Comfort Walking Router</h1>

    <ol class="step-indicator" aria-live="polite">
      {#each ['plan', 'review', 'walk'] as stepName (stepName)}
        <li
          class:active={currentStep === stepName}
          aria-current={currentStep === stepName ? 'step' : undefined}
        >
          {stepName}
        </li>
      {/each}
    </ol>

    <section class="prefs">
      <h2>Preferences</h2>
      <button type="button" on:click={togglePrefs}>
        {showPrefs ? 'Hide preferences' : 'Edit preferences'}
      </button>
      {#if showPrefs && prefs}
        <label>
          Default preference
          <select bind:value={prefs.default_preference}>
            <option value="hot">Hot — prefer shade</option>
            <option value="cloudy">Cloudy — prefer sun</option>
          </select>
        </label>
        <label><input type="checkbox" bind:checked={prefs.prefer_lit} /> Prefer lit streets</label>
        <label><input type="checkbox" bind:checked={prefs.avoid_traffic} /> Avoid busy roads</label>
        <button type="button" on:click={() => handlePrefsSave()}>Save preferences</button>
      {/if}
      {#if prefsError}
        <p class="error">{prefsError}</p>
      {/if}
    </section>
    {#if locateError}
      <div class="locate-notice" role="alert">
        {locateError}
        <button type="button" class="locate-retry" on:click={retryLocate}> Use my location </button>
      </div>
    {/if}
    <Step label="Plan" active={currentStep === 'plan'}>
      <form on:submit|preventDefault={submitRoute}>
        <p class="hint">Set origin and destination on the map search card above.</p>
        {#if activePick}
          <p class="pick-hint" role="status">
            {pickHint(activePick)}{pickBusy ? ' (locating…)' : ' — Esc to cancel'}
          </p>
        {/if}
        {#if pickError}
          <p class="error" role="alert">{pickError}</p>
        {/if}
        <label>
          Preference
          <select bind:value={preference}>
            <option value="">No preference</option>
            <option value="hot">Hot — prefer shade</option>
            <option value="cloudy">Cloudy — prefer sun</option>
          </select>
        </label>
        <label><input type="checkbox" bind:checked={manualOverride} /> Manual override</label>
        <button type="submit" disabled={loading}>
          {loading ? 'Routing…' : 'Find route'}
        </button>
      </form>
    </Step>

    {#if error}
      <p class="error">{error}</p>
    {/if}

    <section class="saved-routes">
      <h2>Saved routes</h2>
      {#if savedError}
        <p class="error">{savedError}</p>
      {/if}
      {#if savedRoutes.length === 0}
        <p class="empty">No saved routes yet.</p>
      {:else}
        <ul class="saved-list">
          {#each savedRoutes as saved (saved.id)}
            <li>
              <span class="saved-name">{saved.name}</span>
              <span class="saved-actions">
                <button type="button" on:click={() => handleRecall(saved.id)}>Recall</button>
                <button type="button" on:click={() => handleDelete(saved.id)}>Delete</button>
              </span>
            </li>
          {/each}
        </ul>
      {/if}
    </section>

    <Step label="Review" active={currentStep === 'review'}>
      {#if route}
        <section class="result">
          <div class="chip">
            {route.preference_source === 'manual'
              ? `Manual: ${route.applied_preference}`
              : `Auto: ${route.applied_preference} ${route.weather.temperature}°C`}
          </div>
          <button type="button" on:click={handleSaveRoute}>Save route</button>
          <h2>{route.name}</h2>
          <p class="stats">
            {(route.distance_m / 1000).toFixed(2)} km ·
            {Math.round(route.duration_s / 60)} min
          </p>
          <p class="score">comfort {route.comfort_score}/100</p>
          {#if route.comfort_profile}
            <ul class="comfort-legend">
              {#each COMFORT_BANDS as b (b.band)}
                <li class="comfort-band comfort-band--{b.band}">
                  <span class="comfort-swatch" style="background:{b.colour}"></span>
                  {b.band} · {b.range}/100
                </li>
              {/each}
            </ul>
            <ul class="comfort-segments">
              {#each comfortRuns as run, index (index)}
                <li class="comfort-segment comfort-band--{run.band}">{formatRun(run)}</li>
              {/each}
            </ul>
          {:else}
            <p class="comfort-unavailable">{COMFORT_UNAVAILABLE_TEXT}</p>
          {/if}
          <Attribution text={route.attribution ?? suggestionAttribution} />
          <h3>Comfort factors</h3>
          <ul class="factors">
            {#each route.explanation as line, index (index)}
              <li>{line}</li>
            {/each}
          </ul>
        </section>
      {/if}
    </Step>

    <Step label="Walk" active={currentStep === 'walk'}>
      <WalkControls route={walkRoute} profile={route?.comfort_profile ?? []} />
      {#if !route}
        <p class="empty">Plan a route first, then start the walk from the Review step.</p>
      {/if}
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
    </Step>
  </aside>

  <!-- Mobile bottom drawer: same controls as the desktop sidebar, shown only
       below 768px so the sidebar and drawer are never visible together. -->
  <section class="bottom-drawer" class:open={drawerOpen} aria-label="Walk controls">
    <button
      type="button"
      class="drawer-toggle"
      aria-expanded={drawerOpen}
      on:click={() => (drawerOpen = !drawerOpen)}
    >
      {drawerOpen ? '▾ Hide controls' : '▴ Show controls'}
    </button>
    <div class="drawer-body">
      {#if route}
        <p class="stats">
          {Math.round(route.duration_s / 60)} min ·
          {(route.distance_m / 1000).toFixed(2)} km · arrival {Math.round(route.duration_s / 60)} min
          · comfort {route.comfort_score}/100
        </p>
      {/if}
      <section class="prefs">
        <h2>Preferences</h2>
        <button type="button" on:click={togglePrefs}>
          {showPrefs ? 'Hide preferences' : 'Edit preferences'}
        </button>
        {#if showPrefs && prefs}
          <label>
            Default preference
            <select bind:value={prefs.default_preference}>
              <option value="hot">Hot — prefer shade</option>
              <option value="cloudy">Cloudy — prefer sun</option>
            </select>
          </label>
          <label><input type="checkbox" bind:checked={prefs.prefer_lit} /> Prefer lit streets</label
          >
          <label
            ><input type="checkbox" bind:checked={prefs.avoid_traffic} /> Avoid busy roads</label
          >
          <button type="button" on:click={() => handlePrefsSave()}>Save preferences</button>
        {/if}
        {#if prefsError}
          <p class="error">{prefsError}</p>
        {/if}
      </section>
      <section class="saved-routes">
        <h2>Saved routes</h2>
        {#if savedError}
          <p class="error">{savedError}</p>
        {/if}
        {#if savedRoutes.length === 0}
          <p class="empty">No saved routes yet.</p>
        {:else}
          <ul class="saved-list">
            {#each savedRoutes as saved (saved.id)}
              <li>
                <span class="saved-name">{saved.name}</span>
                <span class="saved-actions">
                  <button type="button" on:click={() => handleRecall(saved.id)}>Recall</button>
                  <button type="button" on:click={() => handleDelete(saved.id)}>Delete</button>
                </span>
              </li>
            {/each}
          </ul>
        {/if}
      </section>
      <Step label="Plan" active={currentStep === 'plan'}>
        <form on:submit|preventDefault={submitRoute}>
          <p class="hint">Set origin and destination on the map search card above.</p>
          <label>
            Preference
            <select bind:value={preference}>
              <option value="">No preference</option>
              <option value="hot">Hot — prefer shade</option>
              <option value="cloudy">Cloudy — prefer sun</option>
            </select>
          </label>
          <label><input type="checkbox" bind:checked={manualOverride} /> Manual override</label>
          <button type="submit" disabled={loading}>
            {loading ? 'Routing…' : 'Find route'}
          </button>
        </form>
      </Step>
      {#if error}
        <p class="error">{error}</p>
      {/if}
      <Step label="Review" active={currentStep === 'review'}>
        {#if route}
          <section class="result">
            <div class="chip">
              {route.preference_source === 'manual'
                ? `Manual: ${route.applied_preference}`
                : `Auto: ${route.applied_preference} ${route.weather.temperature}°C`}
            </div>
            <button type="button" on:click={handleSaveRoute}>Save route</button>
            <h2>{route.name}</h2>
            <p class="stats">
              {(route.distance_m / 1000).toFixed(2)} km ·
              {Math.round(route.duration_s / 60)} min
            </p>
            <p class="score">comfort {route.comfort_score}/100</p>
            <Attribution text={route.attribution ?? suggestionAttribution} />
          </section>
        {/if}
      </Step>
      <Step label="Walk" active={currentStep === 'walk'}>
        <WalkControls route={walkRoute} profile={route?.comfort_profile ?? []} />
        {#if !route}
          <p class="empty">Plan a route first, then start the walk from the Review step.</p>
        {/if}
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
      </Step>
    </div>
  </section>
</main>

<style>
  :global(body) {
    margin: 0;
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

  @media (min-width: 768px) {
    aside {
      display: block;
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

  form {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
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
    position: absolute;
    inset: 0;
    height: 100%;
    width: 100%;
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

  .comfort-band,
  .comfort-segment {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    padding-left: 0.4rem;
  }

  .comfort-band--good {
    border-left: 4px solid #1a7f37;
  }

  .comfort-band--mixed {
    border-left: 4px solid #b58900;
  }

  .comfort-band--poor {
    border-left: 4px solid #b00020;
  }

  .comfort-swatch {
    width: 12px;
    height: 12px;
    flex: none;
    display: inline-block;
  }

  .comfort-unavailable {
    margin: 0.5rem 0 0;
    font-size: 0.85rem;
    font-style: italic;
    color: #666;
  }

  /* Mobile bottom drawer: collapsed by default, only visible below 768px so the
     sidebar and drawer are never shown at the same size. */
  .bottom-drawer {
    display: none;
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 1000;
    background: #fff;
    box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.15);
  }

  @media not all and (min-width: 768px) {
    .bottom-drawer {
      display: block;
    }
  }

  .drawer-toggle {
    width: 100%;
    border: none;
    border-bottom: 1px solid #ddd;
    background: #fff;
    padding: 0.6rem 1rem;
    text-align: left;
    font-weight: 600;
    cursor: pointer;
  }

  .drawer-body {
    display: none;
    max-height: 60vh;
    overflow-y: auto;
    padding: 1rem;
  }

  .bottom-drawer.open .drawer-body {
    display: block;
  }
</style>
