<script lang="ts">
  /**
   * PreferencesSheet (spec 041, T5 / AC-3, AC-4): the mobile "Walk your way"
   * preferences sheet. Step 1 builds the shell only — scrim, 390×604 bottom
   * sheet, dialog semantics, focus move-in/return and Escape/scrim/close.
   * Later steps fill the sheet body through the default slot.
   */
  import { createEventDispatcher, tick } from 'svelte'

  /** Whether the sheet is mounted. The host page owns the state. */
  export let open = false

  // Svelte treats `export` in the instance script as a prop, so the shade
  // preference union stays local — same values as the desktop panel.
  type ShadePreference = 'hot' | 'cloudy' | 'balanced'

  /** The subset of `route.weather` the weather card renders. */
  interface SheetWeather {
    temperature: number
    cloudCover: number
  }

  /** Current shade preference; two-way bindable with the host page. */
  export let preference: ShadePreference = 'balanced'
  /** Current quieter-streets preference; two-way bindable with the host page. */
  export let avoidTraffic = false
  /** Route weather; the weather card renders nothing without it. */
  export let weather: SheetWeather | null = null

  const dispatch = createEventDispatcher<{
    close: void
    apply: void
    shade: ShadePreference
    quieter: boolean
  }>()

  // Same inlined Material Symbols (Outlined) paths the desktop panel uses,
  // 24×24 with `fill="currentColor"`.
  const wbSunnyPath =
    'M6.76 4.84l-1.8-1.79-1.41 1.41 1.79 1.79 1.42-1.41zM4 10.5H1v2h3v-2zm9-9.95h-2V3.5h2V.55zm7.45 3.91l-1.41-1.41-1.79 1.79 1.41 1.41 1.79-1.79zm-3.21 13.7l1.79 1.8 1.41-1.41-1.8-1.79-1.4 1.4zM20 10.5v2h3v-2h-3zm-8-5c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6-2.69-6-6-6zm-1 16.95h2V19.5h-2v2.95zm-7.45-3.91l1.41 1.41 1.79-1.8-1.41-1.41-1.79 1.8z'

  // Material 'park': tree cover for the shade option.
  const parkPath = 'M17 12h2L12 2 5.05 12H7l-3.9 6h6.92v4h4v-4h6.9L17 12z'

  const cloudPath =
    'M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM19 18H6c-2.21 0-4-1.79-4-4s1.79-4 4-4h.71C7.37 7.69 9.48 6 12 6c3.04 0 5.5 2.46 5.5 5.5v.5H19c1.66 0 3 1.34 3 3s-1.34 3-3 3z'

  // Inlined Material Symbols (Outlined) "close" path, same style as the other
  // redesign icons (24×24, fill="currentColor").
  const closePath =
    'M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z'

  let scrimEl: HTMLDivElement | null = null
  let sheetEl: HTMLElement | null = null
  let closeBtn: HTMLButtonElement | null = null

  let previousFocus: HTMLElement | null = null
  let wasOpen = false

  // Inlined Material Symbols (Outlined) "check" path (24×24, fill="currentColor").
  const checkPath = 'M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z'

  const focusableSelector =
    'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

  function requestClose(): void {
    dispatch('close')
  }

  /** Apply saves the prefs and lets the host close + re-plan. */
  function applyPreferences(): void {
    dispatch('apply')
    requestClose()
  }

  function setShade(value: ShadePreference): void {
    preference = value
    dispatch('shade', value)
  }

  function toggleQuieter(): void {
    avoidTraffic = !avoidTraffic
    dispatch('quieter', avoidTraffic)
  }

  function onScrimClick(event: MouseEvent): void {
    // Only a click on the scrim itself (not bubbled from the sheet) closes.
    if (event.target === scrimEl) requestClose()
  }

  function onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.preventDefault()
      requestClose()
      return
    }
    if (event.key !== 'Tab' || !sheetEl) return
    // Keep focus inside the modal sheet while it is open.
    const focusables = Array.from(sheetEl.querySelectorAll<HTMLElement>(focusableSelector))
    if (focusables.length === 0) {
      event.preventDefault()
      sheetEl.focus()
      return
    }
    const first = focusables[0]
    const last = focusables[focusables.length - 1]
    const active = document.activeElement
    if (event.shiftKey && (active === first || active === sheetEl)) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && active === last) {
      event.preventDefault()
      first.focus()
    }
  }

  // Focus move-in on open, focus return to the opener on close.
  $: if (open !== wasOpen) {
    wasOpen = open
    if (open) {
      previousFocus =
        typeof document !== 'undefined' && document.activeElement instanceof HTMLElement
          ? document.activeElement
          : null
      void tick().then(() => closeBtn?.focus())
    } else {
      previousFocus?.focus()
      previousFocus = null
    }
  }
</script>

{#if open}
  <div class="prefs-scrim" role="presentation" bind:this={scrimEl} on:click={onScrimClick}>
    <section
      class="prefs-sheet"
      data-testid="prefs-sheet"
      role="dialog"
      aria-modal="true"
      aria-labelledby="prefs-title"
      tabindex="-1"
      bind:this={sheetEl}
      on:keydown={onKeydown}
    >
      <span class="prefs-handle" aria-hidden="true"></span>

      <header class="prefs-head">
        <div class="prefs-titles">
          <h2 class="prefs-title" id="prefs-title">Walk your way</h2>
          <p class="prefs-subtitle">Find the route that feels good.</p>
        </div>
        <button
          type="button"
          class="prefs-close"
          data-testid="prefs-close"
          aria-label="Close preferences"
          bind:this={closeBtn}
          on:click={requestClose}
        >
          <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"
            ><path d={closePath} /></svg
          >
        </button>
      </header>

      <div class="prefs-body">
        {#if weather}
          <div class="weather-card" role="status" aria-label="Weather advice">
            <span class="weather-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="currentColor"><path d={wbSunnyPath} /></svg>
            </span>
            <div class="weather-copy">
              <p class="weather-title">
                {weather.cloudCover >= 70 ? 'Overcast' : 'Sunny'}, {Math.round(
                  weather.temperature,
                )}°C
              </p>
              <p class="weather-sub">
                {weather.cloudCover >= 70
                  ? 'A brighter route can feel better.'
                  : 'A shady route can feel cooler.'}
              </p>
            </div>
          </div>
        {/if}

        <div class="shade-heading">
          <p class="shade-title">Sun &amp; shade</p>
          <p class="shade-hint">Your preference</p>
        </div>

        <div class="shade-segment" role="group" aria-label="Sun and shade preference">
          <button
            type="button"
            class="shade-option {preference === 'hot' ? 'active' : ''}"
            data-testid="shade-more"
            aria-pressed={preference === 'hot'}
            on:click={() => setShade('hot')}
          >
            <span class="shade-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="currentColor"><path d={parkPath} /></svg>
            </span>
            <span class="shade-label">More shade</span>
          </button>

          <button
            type="button"
            class="shade-option {preference === 'balanced' ? 'active' : ''}"
            data-testid="shade-balanced"
            aria-pressed={preference === 'balanced'}
            on:click={() => setShade('balanced')}
          >
            <span class="shade-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="currentColor"><path d={cloudPath} /></svg>
            </span>
            <span class="shade-label">Balanced</span>
          </button>

          <button
            type="button"
            class="shade-option {preference === 'cloudy' ? 'active' : ''}"
            data-testid="shade-more-sun"
            aria-pressed={preference === 'cloudy'}
            on:click={() => setShade('cloudy')}
          >
            <span class="shade-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="currentColor"><path d={wbSunnyPath} /></svg>
            </span>
            <span class="shade-label">More sun</span>
          </button>
        </div>

        <p class="shade-helper">Prefer tree cover and shaded streets.</p>

        <button
          type="button"
          class="quieter-row {avoidTraffic ? 'active' : ''}"
          data-testid="quieter-toggle"
          aria-pressed={avoidTraffic}
          on:click={toggleQuieter}
        >
          <span class="quieter-copy">
            <span class="quieter-title">Quieter streets</span>
            <span class="quieter-sub">Stay farther from noisy, busy roads.</span>
          </span>
          <span class="quieter-switch" aria-hidden="true"></span>
        </button>

        <button
          type="button"
          class="prefs-apply"
          data-testid="prefs-apply"
          on:click={applyPreferences}
        >
          <span class="prefs-apply-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="currentColor"><path d={checkPath} /></svg>
          </span>
          <span class="prefs-apply-label">Apply preferences</span>
        </button>
      </div>
    </section>
  </div>
{/if}

<style>
  .prefs-scrim {
    position: fixed;
    inset: 0;
    z-index: 60;
    display: flex;
    align-items: flex-end;
    justify-content: center;
    background: rgb(23 43 36 / 0.35);
  }

  .prefs-sheet {
    box-sizing: border-box;
    position: relative;
    width: 390px;
    height: 604px;
    max-height: 92vh;
    display: flex;
    flex-direction: column;
    padding: 24px 20px 4px;
    background: #ffffff;
    border-radius: 18px 18px 0 0;
    box-shadow: var(--cwr-shadow-card);
    overflow-y: auto;
    animation: prefs-sheet-in 220ms ease-out;
  }

  .prefs-sheet:focus {
    outline: none;
  }

  .prefs-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }

  .prefs-titles {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .prefs-title {
    margin: 0;
    font-size: 23px;
    font-weight: 600;
    line-height: 1.2;
    color: #1b2d24;
  }

  .prefs-subtitle {
    margin: 0;
    font-size: 13px;
    font-weight: 400;
    line-height: 1.35;
    color: #5c6b62;
  }

  .prefs-close {
    flex: none;
    width: 34px;
    height: 34px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    border: none;
    border-radius: 50%;
    background: #f1f5ee;
    color: #1b2d24;
    cursor: pointer;
  }

  .prefs-close svg {
    width: 20px;
    height: 20px;
  }

  .prefs-close:focus-visible {
    outline: 2px solid #2f7d4f;
    outline-offset: 2px;
  }

  .prefs-handle {
    flex: none;
    width: 32px;
    height: 4px;
    margin: 0 auto 14px;
    border-radius: 2px;
    background: #dfe5db;
  }

  .prefs-body {
    display: flex;
    flex: 1;
    min-height: 0;
    flex-direction: column;
    gap: 16px;
    margin-top: 18px;
  }

  /* Weather card 350×60 (design-spec §Mobile preferences sheet). */
  .weather-card {
    box-sizing: border-box;
    width: 100%;
    height: 60px;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 0 14px;
    border-radius: 12px;
    background: var(--cwr-sun-bg);
  }

  .weather-icon {
    flex: none;
    display: inline-flex;
    color: #6e5428;
  }

  .weather-icon svg {
    width: 28px;
    height: 28px;
  }

  .weather-copy {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .weather-title {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    line-height: 1.25;
    color: #6e5428;
  }

  .weather-sub {
    margin: 0;
    font-size: 12px;
    font-weight: 400;
    line-height: 1.3;
    color: #8d774d;
  }

  .shade-heading {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
  }

  .shade-title {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    line-height: 1.25;
    color: var(--cwr-ink, #1b2d24);
  }

  .shade-hint {
    margin: 0;
    font-size: 11px;
    font-weight: 400;
    color: #738078;
  }

  /* Segmented 350×64 with 112×56 options and 20 px icons. */
  .shade-segment {
    box-sizing: border-box;
    width: 100%;
    height: 64px;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 4px;
    padding: 4px;
    border-radius: 12px;
    background: #f1f5ee;
  }

  .shade-option {
    box-sizing: border-box;
    width: 112px;
    max-width: 100%;
    height: 56px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    padding: 0;
    border: none;
    border-radius: 9px;
    background: transparent;
    color: #5c6b62;
    font-family: inherit;
    cursor: pointer;
  }

  .shade-option.active {
    background: #ffffff;
    color: var(--cwr-brand, #17765c);
    box-shadow:
      inset 0 0 0 1.5px var(--cwr-brand, #17765c),
      0 1px 2px rgb(23 43 36 / 0.12);
  }

  .shade-icon {
    display: inline-flex;
  }

  .shade-icon svg {
    width: 20px;
    height: 20px;
  }

  .shade-label {
    font-size: 11px;
    font-weight: 600;
    line-height: 1.2;
  }

  .shade-option:focus-visible {
    outline: 2px solid #2f7d4f;
    outline-offset: 2px;
  }

  .shade-helper {
    margin: 0;
    font-size: 12px;
    font-weight: 400;
    line-height: 1.35;
    color: #738078;
  }

  .quieter-row {
    box-sizing: border-box;
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 4px 0;
    border: none;
    border-radius: 0;
    background: transparent;
    color: var(--cwr-ink, #1b2d24);
    font-family: inherit;
    text-align: left;
    cursor: pointer;
  }

  .quieter-copy {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .quieter-title {
    font-size: 14px;
    font-weight: 600;
    line-height: 1.25;
  }

  .quieter-sub {
    font-size: 12px;
    font-weight: 400;
    line-height: 1.3;
    color: #738078;
  }

  .quieter-switch {
    position: relative;
    flex: none;
    width: 44px;
    height: 26px;
    border-radius: 13px;
    background: #dbe3d6;
    transition: background 160ms ease-out;
  }

  .quieter-switch::after {
    content: '';
    position: absolute;
    top: 3px;
    left: 3px;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: #ffffff;
    transition: transform 160ms ease-out;
  }

  .quieter-row.active .quieter-switch {
    background: var(--cwr-brand, #2f7d4f);
  }

  .quieter-row.active .quieter-switch::after {
    transform: translateX(18px);
  }

  .quieter-row:focus-visible {
    outline: 2px solid #2f7d4f;
    outline-offset: 2px;
  }

  /* Footer "Apply preferences" 350×52, brand, white 14/600, check icon. */
  .prefs-apply {
    box-sizing: border-box;
    width: 100%;
    height: 48px;
    margin-top: auto;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 0 16px;
    border: none;
    border-radius: 999px;
    background: var(--cwr-brand, #2f7d4f);
    color: #ffffff;
    font-family: inherit;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
  }

  .prefs-apply-icon {
    display: inline-flex;
  }

  .prefs-apply-icon svg {
    width: 20px;
    height: 20px;
  }

  .prefs-apply:focus-visible {
    outline: 2px solid #2f7d4f;
    outline-offset: 2px;
  }

  @keyframes prefs-sheet-in {
    from {
      transform: translateY(100%);
    }
    to {
      transform: translateY(0);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .prefs-sheet {
      animation: none;
    }

    .quieter-switch,
    .quieter-switch::after {
      transition: none;
    }
  }
</style>
