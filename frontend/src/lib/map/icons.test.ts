/**
 * Unit tests for walk-mode map marker icons — spec 014 (walk guidance UX),
 * task T4 (AC-1, AC-2).
 */
import { describe, expect, it } from 'vitest'
import {
  END_PIN_LABEL,
  END_PIN_SVG,
  PERSON_ICON_LABEL,
  PERSON_WALKING_SVG,
  PIN_SHAPE_PATH,
  START_PIN_LABEL,
  START_PIN_SVG,
  endPinIcon,
  personIcon,
  startPinIcon,
  type DivIconConfig,
} from './icons'

/** All icon factories must return a divIcon config with these fields. */
const ALL_ICONS: Array<[string, DivIconConfig]> = [
  ['personIcon', personIcon()],
  ['startPinIcon', startPinIcon()],
  ['endPinIcon', endPinIcon()],
]

describe('walk-mode map icon SVG strings', () => {
  it('embeds the shared teardrop pin shape in both endpoint pins', () => {
    expect(START_PIN_SVG).toContain(`d="${PIN_SHAPE_PATH}"`)
    expect(END_PIN_SVG).toContain(`d="${PIN_SHAPE_PATH}"`)
  })

  it('labels the start pin "A" and the end pin "B"', () => {
    expect(START_PIN_SVG).toContain('>A</text>')
    expect(END_PIN_SVG).toContain('>B</text>')
  })

  it('colors the start pin blue and the end pin red (AC-1, AC-2)', () => {
    expect(START_PIN_SVG).toContain('fill="#1d4ed8"')
    expect(END_PIN_SVG).toContain('fill="#dc2626"')
    expect(START_PIN_SVG).not.toContain('fill="#dc2626"')
    expect(END_PIN_SVG).not.toContain('fill="#1d4ed8"')
  })

  it('renders the person-walking glyph for the live position marker', () => {
    expect(PERSON_WALKING_SVG).toContain('<svg')
    expect(PERSON_WALKING_SVG).toContain('viewBox="0 0 16 16"')
    expect(PERSON_WALKING_SVG).toContain('<path')
  })
})

describe('walk-mode map icon accessible labels', () => {
  it('exposes non-empty labels for every icon (AC-1, AC-2)', () => {
    expect(PERSON_ICON_LABEL.trim().length).toBeGreaterThan(0)
    expect(START_PIN_LABEL.trim().length).toBeGreaterThan(0)
    expect(END_PIN_LABEL.trim().length).toBeGreaterThan(0)
  })

  it('announces each label via role="img" aria-label in the icon html', () => {
    expect(personIcon().html).toContain(`aria-label="${PERSON_ICON_LABEL}"`)
    expect(startPinIcon().html).toContain(`aria-label="${START_PIN_LABEL}"`)
    expect(endPinIcon().html).toContain(`aria-label="${END_PIN_LABEL}"`)
  })
})

describe('walk-mode map divIcon configs', () => {
  it.each(ALL_ICONS)(
    '%s returns a divIcon config with html, iconSize, iconAnchor',
    (_name, icon) => {
      expect(typeof icon.html).toBe('string')
      expect(icon.html.length).toBeGreaterThan(0)
      expect(icon.className.length).toBeGreaterThan(0)
      expect(icon.iconSize).toEqual([28, 28])
      expect(icon.iconAnchor).toHaveLength(2)
      expect(icon.iconAnchor[0]).toBe(icon.iconSize[0] / 2)
    },
  )

  it('anchors the person marker at its center', () => {
    expect(personIcon().iconAnchor).toEqual([14, 14])
  })

  it('anchors the endpoint pins at the teardrop tip', () => {
    expect(startPinIcon().iconAnchor).toEqual([14, 28])
    expect(endPinIcon().iconAnchor).toEqual([14, 28])
  })

  it('wraps each pin html in a labelled span', () => {
    expect(startPinIcon().html).toContain('role="img"')
    expect(endPinIcon().html).toContain('role="img"')
    expect(personIcon().html).toContain('role="img"')
  })
})
