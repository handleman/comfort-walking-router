<script lang="ts">
  interface Waypoint {
    lat: number;
    lng: number;
  }

  interface LineStringGeometry {
    type: 'LineString';
    coordinates: [number, number][];
  }

  interface Weather {
    temperature: number;
    cloudCover: number;
  }

  interface Route {
    id: string;
    name: string;
    description?: string;
    waypoints: Waypoint[];
    status: 'active' | 'inactive' | 'archived';
    timestamp: string;
    comfort_score: number;
    explanation: string[];
    geometry: LineStringGeometry;
    distance_m: number;
    duration_s: number;
    applied_preference: string;
    preference_source: 'auto' | 'manual';
    weather: Weather;
  }

  import { onMount } from 'svelte';
  import L from 'leaflet';

  let mapElement: HTMLDivElement;
  let map: L.Map | null = null;
  let routeLayer: L.LayerGroup | null = null;

  let start = '';
  let end = '';
  let preference = '';
  let route: Route | null = null;
  let error = '';
  let loading = false;
  let manualOverride = false;

  onMount(() => {
    map = L.map(mapElement).setView([48.137, 11.575], 12);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
  });

  async function submitRoute() {
    error = '';
    loading = true;
    try {
      const response = await fetch('/route', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          start,
          end,
          preference: manualOverride ? (preference || null) : null
        })
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.message || data.detail || `Route request failed (${response.status})`);
      }
      route = data;
      drawRoute();
    } catch (err) {
      route = null;
      error = err instanceof Error ? err.message : String(err);
    } finally {
      loading = false;
    }
  }

  function drawRoute() {
    if (!map || !route || !route.geometry) return;
    if (routeLayer) {
      routeLayer.remove();
    }
    const layer = L.layerGroup().addTo(map);
    routeLayer = layer;
    const line = L.geoJSON(route.geometry).addTo(layer);
    route.waypoints.forEach((point, index) => {
      L.circleMarker([point.lat, point.lng], { radius: 6 })
        .bindTooltip(index === 0 ? 'Start' : 'End')
        .addTo(layer);
    });
    map.fitBounds(line.getBounds(), { padding: [24, 24] });
  }
</script>

<svelte:head>
  <title>Comfort Walking Router</title>
</svelte:head>

<main>
  <aside>
    <h1>Comfort Walking Router</h1>
    <form on:submit|preventDefault={submitRoute}>
      <label>
        Start
        <input bind:value={start} placeholder="e.g. Marienplatz, Munich" required />
      </label>
      <label>
        End
        <input bind:value={end} placeholder="e.g. Englischer Garten" required />
      </label>
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

    {#if route}
      <section class="result">
        <div class="chip">{route.preference_source === 'manual' ? 'Manual' : `Auto: ${route.applied_preference} ${route.weather.temperature}°C`}</div>
        <h2>{route.name}</h2>
        <p class="stats">
          {(route.distance_m / 1000).toFixed(2)} km ·
          {Math.round(route.duration_s / 60)} min
        </p>
        <p class="score">comfort {route.comfort_score}/100</p>
        <ul class="factors">
          {#each route.explanation as line}
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
    font-family: system-ui, -apple-system, sans-serif;
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
