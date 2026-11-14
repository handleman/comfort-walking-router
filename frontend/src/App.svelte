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
    duration_s: number
    applied_preference: string
    preference_source: 'auto' | 'manual'
    weather: Weather
  }

  import { onMount } from 'svelte'
  import L from 'leaflet'
  import { personIcon, startPinIcon, endPinIcon } from './lib/map/icons'
  import { pickHint, reverseLabel, togglePickRole } from './lib/map/picker'
  import type { PickRole } from './lib/map/picker'
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
  let error = ''
  let loading = false
  let manualOverride = false
  let savedRoutes: SavedRoute[] = []
  let prefs: Prefs | null = null
  let showPrefs = false
  let savedError = ''
  let prefsError = ''
  let locateError = ''
  let currentMarker: L.Marker | null = null
  let startCoords: [number, number] | null = null
  let endCoords: [number, number] | null = null
  let startMarker: L.Marker | null = null
  let endMarker: L.Marker | null = null

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
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map)
    ensureToken()
    map.locate({ setView: true, maxZoom: 16, timeout: 8000, enableHighAccuracy: true })
    map.on('locationfound', onLocationFound)
    map.on('locationerror', onLocationError)
    map.on('click', onMapClick)
    loadSaved()
    loadPrefs()
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
    if (currentMarker) {
      currentMarker.setLatLng([lat, lng])
    } else {
      currentMarker = L.marker([lat, lng], {
        icon: L.divIcon(personIcon()),
      }).addTo(map)
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

  async function submitRoute() {
    error = ''
    loading = true
    try {
      const response = await fetch('/route', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          start,
          end,
          preference: manualOverride ? preference || null : null,
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
      drawRoute()
    } catch (err) {
      route = null
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
    const line = L.geoJSON(route.geometry).addTo(layer)
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
  <aside>
    <h1>Comfort Walking Router</h1>

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
    <form on:submit|preventDefault={submitRoute}>
      <label>
        Start
        <span class="pick-row">
          <input
            bind:value={start}
            on:input={clearStartCoords}
            placeholder="e.g. Marienplatz, Munich"
            required
          />
          <button
            type="button"
            class="pick-btn"
            aria-pressed={activePick === 'start'}
            aria-label="Pick start on map"
            on:click={() => beginPick('start')}>⌖</button
          >
        </span>
      </label>
      <label>
        End
        <span class="pick-row">
          <input
            bind:value={end}
            on:input={clearEndCoords}
            placeholder="e.g. Englischer Garten"
            required
          />
          <button
            type="button"
            class="pick-btn"
            aria-pressed={activePick === 'end'}
            aria-label="Pick end on map"
            on:click={() => beginPick('end')}>⌖</button
          >
        </span>
      </label>
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

    {#if route}
      <section class="result">
        <div class="chip">
          {route.preference_source === 'manual'
            ? 'Manual'
            : `Auto: ${route.applied_preference} ${route.weather.temperature}°C`}
        </div>
        <button type="button" on:click={handleSaveRoute}>Save route</button>
        <h2>{route.name}</h2>
        <p class="stats">
          {(route.distance_m / 1000).toFixed(2)} km ·
          {Math.round(route.duration_s / 60)} min
        </p>
        <p class="score">comfort {route.comfort_score}/100</p>
        <h3>Comfort factors</h3>
        <ul class="factors">
          {#each route.explanation as line, index (index)}
            <li>{line}</li>
          {/each}
        </ul>
      </section>
    {/if}
  </aside>

  <div id="map" bind:this={mapElement}></div>
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
    display: grid;
    grid-template-columns: minmax(280px, 360px) 1fr;
    min-height: 100vh;
  }

  aside {
    padding: 1rem;
    overflow-y: auto;
    border-right: 1px solid #ddd;
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
    min-height: 400px;
    height: 100vh;
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

  @media (max-width: 720px) {
    main {
      grid-template-columns: 1fr;
    }

    #map {
      height: 60vh;
      min-height: 320px;
    }
  }
</style>
