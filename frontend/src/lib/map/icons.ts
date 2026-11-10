/*!
 * Walk-mode map marker icons — spec 014 (walk guidance UX), task T4 (AC-1, AC-2).
 *
 * The `person-walking` glyph below is based on Bootstrap Icons, which is
 * distributed under the MIT License:
 *
 *   MIT License
 *
 *   Copyright (c) 2019-2024 The Bootstrap Authors
 *
 *   Permission is hereby granted, free of charge, to any person obtaining a copy
 *   of this software and associated documentation files (the "Software"), to deal
 *   in the Software without restriction, including without limitation the rights
 *   to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 *   copies of the Software, and to permit persons to whom the Software is
 *   furnished to do so, subject to the following conditions:
 *
 *   The above copyright notice and this permission notice shall be included in
 *   all copies or substantial portions of the Software.
 *
 *   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 *   IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 *   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 *   AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 *   LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 *   OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 *   THE SOFTWARE.
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
 * Inline Bootstrap Icons `person-walking` SVG string (16x16 viewBox,
 * `fill="currentColor"` so it inherits the marker's CSS color).
 */
export const PERSON_WALKING_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true" focusable="false">' +
  '<path d="M9.5 1.5a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0ZM6.44 3.75a.75.75 0 0 1 .73.75v3.06l-.01.02-.01.03-.01.02a.75.75 0 0 1-.16.26l-2.2 2.2 2.2 2.2a.75.75 0 1 1-1.06 1.06l-2.73-2.73a.75.75 0 0 1 0-1.06l2.2-2.2V4.5a.75.75 0 0 1 .75-.75h.3Z"/>' +
  '<path fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" d="M7.2 7.8l2.1 2.5-.7 3.9M7.2 7.8 5.5 10.2l-1.3 3.9"/>' +
  '</svg>'

/** Shared teardrop pin shape (24x24 viewBox) used by both route-endpoint pins. */
export const PIN_SHAPE_PATH = 'M12 2a7 7 0 0 0-7 7c0 5.25 7 13 7 13s7-7.75 7-13a7 7 0 0 0-7-7Z'

/** Blue start-pin SVG string with the "A" label (AC-1). */
export const START_PIN_SVG =
  `<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" aria-hidden="true" focusable="false">` +
  `<path fill="#1d4ed8" stroke="#ffffff" stroke-width="1.2" d="${PIN_SHAPE_PATH}"/>` +
  `<text x="12" y="9" dy="0.32em" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="9" font-weight="700" fill="#ffffff">A</text>` +
  `</svg>`

/** Red end-pin SVG string with the "B" label (AC-2). */
export const END_PIN_SVG =
  `<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" aria-hidden="true" focusable="false">` +
  `<path fill="#dc2626" stroke="#ffffff" stroke-width="1.2" d="${PIN_SHAPE_PATH}"/>` +
  `<text x="12" y="9" dy="0.32em" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="9" font-weight="700" fill="#ffffff">B</text>` +
  `</svg>`

/** Accessible label announced for the live walker-position marker (AC-1). */
export const PERSON_ICON_LABEL = 'Your current position (walking)'

/** Accessible label announced for the blue start pin (AC-1). */
export const START_PIN_LABEL = 'Walk start'

/** Accessible label announced for the red end pin (AC-2). */
export const END_PIN_LABEL = 'Walk destination'

/** Div-icon config for the live walker position (Bootstrap person glyph). */
export function personIcon(): DivIconConfig {
  return {
    html:
      `<span class="walk-icon walk-person" role="img" aria-label="${PERSON_ICON_LABEL}">` +
      `${PERSON_WALKING_SVG}</span>`,
    className: 'walk-person-marker',
    iconSize: [28, 28],
    iconAnchor: [14, 14],
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
