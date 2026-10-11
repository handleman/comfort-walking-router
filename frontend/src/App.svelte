<script>
  import { onMount } from 'svelte';
  import L from 'leaflet';

  let map;
  let startInput = '';
  let endInput = '';
  let isHot = false;
  let isCloudy = false;

  let routeResponse = null;

  onMount(() => {
    const mapElement = document.getElementById('map');
    if (mapElement) {
      map = L.map(mapElement).setView([51.505, -0.09], 13);
      L.tileLayer('https://tile.openstreet.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
      }).addTo(map);
    }
  });

  async function fetchRoute() {
    const response = await fetch('/route', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ start: startInput, end: endInput, hot: isHot, cloudy: isCloudy })
    });
    routeResponse = await response.json();
  }

  function drawRoute() {
    if (routeResponse && map) {
      L.geoJSON(routeResponse).addTo(map);
    }
  }
</script>

<div id="map"></div>

<form>
  <input bind:value={startInput} placeholder="Start" />
  <input bind:value={endInput} placeholder="End" />
  <label>
    Hot
    <input type="checkbox" bind:checked={isHot} />
  </label>
  <label>
    Cloudy
    <input type="checkbox" bind:checked={isCloudy} />
  </label>
</form>

{#if routeResponse}
  <div class="explanation">
    <p>Distance: {routeResponse.distance} km</p>
    <p>Time: {routeResponse.time} min</p>
    <p>Comfort Factors: {JSON.stringify(routeResponse.comfortFactors)}</p>
  </div>
{/if}