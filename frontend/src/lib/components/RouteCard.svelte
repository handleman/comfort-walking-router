<script lang="ts">
  // Desktop route card (spec 041, T3 / AC-2). One route, honest: the single
  // planned walk with its duration, distance, profile-derived shade meta and
  // the comfort segments + explanation lines it already exposes. No second or
  // fake alternative route is rendered here. All state and handlers live in
  // App.svelte and are passed in.
  import { COMFORT_UNAVAILABLE_TEXT, formatRun, mergeBandRuns } from '../map/comfortBands'
  import type { ComfortProfileSegment } from '../map/comfortBands'
  import Attribution from './Attribution.svelte'
  import { shadedPercent } from '../routeMeta'

  // Structural subset of App.svelte's Route: everything this card renders.
  interface RouteCardRoute {
    name: string
    duration_s: number
    distance_m: number
    applied_preference: string
    preference_source: 'auto' | 'manual'
    weather: { temperature: number }
    comfort_profile: ComfortProfileSegment[] | null
    attribution?: string
    explanation: string[]
  }

  export let route: RouteCardRoute | null = null
  /** Comfort profile segments; empty until a route with profile data exists. */
  export let profile: ComfortProfileSegment[] = []
  /** `Quieter` meta only shows when the walk avoids busy roads. */
  export let avoidTraffic = false
  export let suggestionAttribution = ''
  /** Mobile sheet variant: duration/distance/meta + CTA only (no chip,
   *  band list or explanation disclosure). */
  export let compact = false

  const uid = `route-card-${Math.random().toString(36).slice(2, 9)}`

  // Shaded share of the covered distance; hidden without profile data.
  $: shaded = shadedPercent(profile && profile.length > 0 ? profile : route?.comfort_profile)

  $: comfortRuns = route && route.comfort_profile ? mergeBandRuns(route.comfort_profile) : []

  // Material Design glyphs kept inline: the card only needs these two.
  const SUN_PATH =
    'M6.76 4.84l-1.8-1.79-1.41 1.41 1.79 1.79 1.42-1.41zM4 10.5H1v2h3v-2zm9-9.95h-2V3.5h2V.55zm7.45 3.91l-1.41-1.41-1.79 1.79 1.41 1.41 1.79-1.79zm-3.21 13.7l1.79 1.8 1.41-1.41-1.8-1.79-1.4 1.4zM20 10.5v2h3v-2h-3zm-8-5c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6-2.69-6-6-6zm-1 16.95h2V19.5h-2v2.95zm-7.45-3.91l1.41 1.41 1.79-1.8-1.41-1.41-1.79 1.8z'
  const QUIET_PATH =
    'M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z'
</script>

<section class="route-summary" aria-labelledby="{uid}-title">
  <h2 id="{uid}-title" class="visually-hidden">Route summary</h2>
  {#if route}
    <article class="route-card">
      <div class="headline">
        <span class="duration">{Math.round(route.duration_s / 60)} min</span>
        <span class="distance">{(route.distance_m / 1000).toFixed(1)} km</span>
        <span class="best-fit">Best fit</span>
      </div>
      {#if shaded !== null || avoidTraffic}
        <p class="meta">
          {#if shaded !== null}
            <span class="meta-item">
              <span class="icon" aria-hidden="true"
                ><svg viewBox="0 0 24 24" fill="currentColor"><path d={SUN_PATH} /></svg></span
              >
              {shaded}% shaded
            </span>
          {/if}
          {#if avoidTraffic}
            <span class="meta-item">
              <span class="icon" aria-hidden="true"
                ><svg viewBox="0 0 24 24" fill="currentColor"><path d={QUIET_PATH} /></svg></span
              >
              Quieter
            </span>
          {/if}
        </p>
      {/if}
      <Attribution text={route.attribution ?? suggestionAttribution} />
    </article>

    {#if !compact}
      <details class="route-details" data-testid="route-details">
        <summary>Why this route?</summary>
        <div class="chip">
          {route.preference_source === 'manual'
            ? `Manual: ${route.applied_preference}`
            : `Auto: ${route.applied_preference} ${route.weather.temperature}°C`}
        </div>
        {#if route.comfort_profile}
          <ul class="comfort-segments" aria-label="Comfort profile">
            {#each comfortRuns as run, index (index)}
              <li class="comfort-segment comfort-band comfort-band--{run.band}">
                {formatRun(run)}
              </li>
            {/each}
          </ul>
        {:else}
          <p class="comfort-unavailable">{COMFORT_UNAVAILABLE_TEXT}</p>
        {/if}
        <ul class="factors">
          {#each route.explanation as line, index (index)}
            <li>{line}</li>
          {/each}
        </ul>
      </details>
    {/if}
  {:else}
    <p class="empty">No route planned yet.</p>
  {/if}
</section>

<style>
  .visually-hidden {
    position: absolute;
    width: 1px;
    height: 1px;
    margin: -1px;
    padding: 0;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
    border: 0;
  }

  .route-details {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-top: 6px;
    color: var(--cwr-muted);
    font-size: 11px;
  }

  .route-details summary {
    cursor: pointer;
    font-size: 11px;
  }

  .route-card {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 18px 20px;
    border-radius: 14px;
    border: 1px solid var(--cwr-line-strong);
    background: #ffffff;
  }

  .chip {
    align-self: flex-start;
    padding: 4px 10px;
    border-radius: 999px;
    background: var(--cwr-brand-soft);
    color: #326647;
    font-size: 12px;
    font-weight: 500;
    line-height: 16px;
  }

  .headline {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 10px;
  }

  .duration {
    color: var(--cwr-brand);
    font-size: 26px;
    font-weight: 600;
    line-height: 32px;
  }

  .distance {
    color: #738078;
    font-size: 12px;
    font-weight: 400;
    line-height: 16px;
  }

  .best-fit {
    padding: 3px 10px;
    border-radius: 999px;
    background: var(--cwr-brand-soft);
    color: #326647;
    font-size: 12px;
    font-weight: 500;
    line-height: 16px;
  }

  .meta {
    display: flex;
    align-items: center;
    gap: 14px;
    margin: 0;
    color: #42705b;
    font-size: 11px;
    font-weight: 500;
    line-height: 14px;
  }

  .meta-item {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }

  .meta .icon {
    display: inline-flex;
    width: 14px;
    height: 14px;
  }

  .meta svg {
    width: 14px;
    height: 14px;
  }

  .comfort-segments {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .comfort-segment {
    padding: 2px 8px;
    border-radius: 999px;
    background: #f1f5ee;
    font-size: 11px;
    font-weight: 500;
  }

  .comfort-unavailable {
    margin: 0;
    color: #738078;
    font-size: 12px;
  }

  .why {
    font-size: 12px;
  }

  .why summary {
    cursor: pointer;
    color: #326647;
    font-size: 12px;
    font-weight: 600;
  }

  .factors {
    margin: 6px 0 0;
    padding-left: 18px;
    color: #42705b;
    font-size: 12px;
    line-height: 18px;
  }

  .empty {
    margin: 0;
    color: #738078;
    font-size: 13px;
  }
</style>
