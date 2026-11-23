/*!
 * Walk-mode map marker icons — spec 014 (walk guidance UX), task T4 (AC-1, AC-2).
 *
 * The `directions_walk` glyph and the `place`-based endpoint pins are the
 * inlined Material Symbols SVGs from `material.ts` (24x24 viewBox,
 * `fill="currentColor"`).
 */

/**
 * Options accepted by Leaflet's `L.divIcon()` factory (the subset we use).
 * Pass a config straight through: `L.divIcon(personIcon())`.
 */
export interface DivIconConfig {
  /** Inline HTML rendered inside the marker's div. */
  html: string
  /** Replaces the default `leaflet-div-icon` class (drops the white box). */
  className: string
  /** Pixel size of the marker div. */
  iconSize: [number, number]
  /** Pixel offset from the marker's geographic point to the div's anchor. */
  iconAnchor: [number, number]
  /** Pixel offset from the icon anchor to the popup tip. */
  popupAnchor?: [number, number]
}

/**
 * Material Symbols `directions_walk` SVG string (24x24 viewBox,
 * `fill="currentColor"` so it inherits the marker's CSS color),
 * reused from the inlined icon set in `material.ts`.
 */
import { directionsWalk, place, svgPath } from './material'

export const PERSON_WALKING_SVG = directionsWalk

/**
 * Material Symbols `place` glyph path (24x24 viewBox), extracted from the
 * inlined `place` SVG in `material.ts` so the route-endpoint pins reuse the
 * real icon shape from a single source of truth.
 */
export const PIN_SHAPE_PATH = svgPath(place)

/** Blue start-pin SVG string based on the Material `place` glyph (AC-1). */
export const START_PIN_SVG =
  `<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" aria-hidden="true" focusable="false">` +
  `<path fill="#1d4ed8" stroke="#ffffff" stroke-width="1.2" d="${PIN_SHAPE_PATH}"/>` +
  `</svg>`

/** Red end-pin SVG string based on the Material `place` glyph (AC-2). */
export const END_PIN_SVG =
  `<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" aria-hidden="true" focusable="false">` +
  `<path fill="#dc2626" stroke="#ffffff" stroke-width="1.2" d="${PIN_SHAPE_PATH}"/>` +
  `</svg>`

/** Accessible label announced for the live walker-position marker (AC-1). */
export const PERSON_ICON_LABEL = 'Your current position (walking)'

/** Accessible label announced for the blue start pin (AC-1). */
export const START_PIN_LABEL = 'Walk start'

/** Accessible label announced for the red end pin (AC-2). */
export const END_PIN_LABEL = 'Walk destination'

/** Div-icon config for the live walker position (Material `directions_walk`). */
export function personIcon(): DivIconConfig {
  return {
    html:
      `<span class="walk-icon walk-person" role="img" aria-label="${PERSON_ICON_LABEL}" ` +
      `style="display:flex;align-items:center;justify-content:center;width:34px;height:34px;` +
      `background:#1d4ed8;color:#fff;border:3px solid #fff;border-radius:50%;` +
      `box-shadow:0 1px 5px rgba(0,0,0,.5);box-sizing:border-box;">` +
      `${PERSON_WALKING_SVG}</span>`,
    className: 'walk-person-marker',
    iconSize: [34, 34],
    iconAnchor: [17, 17],
  }
}

/** Div-icon config for the blue "A" start pin (tip anchored at the coordinate). */
export function startPinIcon(): DivIconConfig {
  return {
    html:
      `<span class="walk-icon walk-pin walk-pin-start" role="img" aria-label="${START_PIN_LABEL}">` +
      `${START_PIN_SVG}</span>`,
    className: 'walk-pin-marker',
    iconSize: [28, 28],
    iconAnchor: [14, 28],
    popupAnchor: [0, -26],
  }
}

/** Div-icon config for the red "B" end pin (tip anchored at the coordinate). */
export function endPinIcon(): DivIconConfig {
  return {
    html:
      `<span class="walk-icon walk-pin walk-pin-end" role="img" aria-label="${END_PIN_LABEL}">` +
      `${END_PIN_SVG}</span>`,
    className: 'walk-pin-marker',
    iconSize: [28, 28],
    iconAnchor: [14, 28],
    popupAnchor: [0, -26],
  }
}
