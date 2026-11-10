<script lang="ts">
  /**
   * Search combobox (spec 014-walk-guidance-ux, task T7, AC-4):
   * role="combobox" text input bound to `query` with a role="listbox"
   * popup of role="option" items fed by the debounced fetchSuggestions
   * client. Arrow keys move the active option, Enter selects, Esc closes,
   * and mouse/touch clicks select directly. The chosen suggestion is
   * exposed via the bindable `selected` prop.
   */
  import { createSuggestionFetcher } from '../search/suggestions'
  import type { Suggestion } from '../search/suggestions'

  /** Base URL for the geocode/suggest endpoint. */
  export let baseUrl = ''

  /** Currently selected suggestion; bind to read the user's choice. */
  export let selected: Suggestion | null = null

  let query = ''
  let suggestions: Suggestion[] = []
  let open = false
  let activeIndex = -1
  let suppressSearch = false
  let listEl: HTMLUListElement | null = null

  let fetchSuggestions: (q: string) => Promise<Suggestion[]> = createSuggestionFetcher(baseUrl)
  $: fetchSuggestions = createSuggestionFetcher(baseUrl)

  $: void runSearch(query)

  async function runSearch(q: string): Promise<void> {
    if (suppressSearch) {
      suppressSearch = false
      return
    }
    const results = await fetchSuggestions(q)
    suggestions = results
    activeIndex = -1
    open = results.length > 0
  }

  function select(suggestion: Suggestion): void {
    if (query !== suggestion.label) suppressSearch = true
    selected = suggestion
    query = suggestion.label
    open = false
    activeIndex = -1
  }

  function move(delta: number): void {
    if (suggestions.length === 0) return
    activeIndex = (activeIndex + delta + suggestions.length) % suggestions.length
    scrollActiveIntoView()
  }

  function scrollActiveIntoView(): void {
    if (!listEl || activeIndex < 0) return
    const el = listEl.children[activeIndex] as HTMLElement | undefined
    el?.scrollIntoView({ block: 'nearest' })
  }

  function onKeydown(event: KeyboardEvent): void {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      move(1)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      move(-1)
    } else if (event.key === 'Enter') {
      if (activeIndex >= 0 && activeIndex < suggestions.length) {
        event.preventDefault()
        select(suggestions[activeIndex])
      }
    } else if (event.key === 'Escape') {
      open = false
      activeIndex = -1
    }
  }
</script>

<div class="search-combobox">
  <input
    type="text"
    role="combobox"
    aria-autocomplete="list"
    aria-controls="search-suggestions"
    aria-expanded={open}
    aria-activedescendant={activeIndex >= 0 ? `search-option-${activeIndex}` : undefined}
    placeholder="Search destination"
    bind:value={query}
    on:keydown={onKeydown}
    on:focus={() => {
      if (suggestions.length > 0) open = true
    }}
  />
  {#if open}
    <ul class="suggestions" id="search-suggestions" role="listbox" bind:this={listEl}>
      {#each suggestions as suggestion, i (suggestion.value + suggestion.label)}
        <li
          id={`search-option-${i}`}
          class="suggestion"
          class:active={i === activeIndex}
          role="option"
          aria-selected={i === activeIndex}
          on:click={() => select(suggestion)}
          on:touchend={() => select(suggestion)}
          on:keydown={() => {}}
        >
          {suggestion.label}
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .search-combobox {
    position: relative;
  }
  .suggestions {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    margin: 0;
    padding: 0;
    list-style: none;
    background: #fff;
    border: 1px solid #ccc;
    max-height: 16rem;
    overflow-y: auto;
    z-index: 10;
  }
  .suggestion {
    padding: 0.4rem 0.6rem;
    cursor: pointer;
  }
  .suggestion.active {
    background: #eef;
  }
</style>
