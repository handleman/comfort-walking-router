import { describe, expect, it } from 'vitest'

import {
  quieterVisible,
  shadeLabel,
  shadedPercent,
  weatherAdvice,
  weatherCondition,
} from './routeMeta'

describe('shadedPercent', () => {
  it('returns the shaded share of the covered distance', () => {
    expect(
      shadedPercent([
        { from_m: 0, to_m: 720, factor: 'shade', score: 58, label: 'sunny side' },
        { from_m: 720, to_m: 1000, factor: 'sun', score: 85, label: 'exposed' },
      ]),
    ).toBe(72)
  })

  it('returns null without profile data', () => {
    expect(shadedPercent(null)).toBeNull()
    expect(shadedPercent([])).toBeNull()
  })

  it('ignores zero-length segments', () => {
    expect(
      shadedPercent([{ from_m: 100, to_m: 100, factor: 'shade', score: 50, label: 'shaded' }]),
    ).toBeNull()
  })
})

describe('weatherAdvice', () => {
  it('recommends shade in hot sun', () => {
    expect(weatherAdvice({ temperature: 26, cloudCover: 20 })).toEqual({
      title: 'A little shade goes a long way',
      sub: 'Sunny, 26°C · shade recommended',
    })
  })

  it('recommends sun when overcast', () => {
    expect(weatherAdvice({ temperature: 10, cloudCover: 90 })).toEqual({
      title: 'A brighter route feels better',
      sub: 'Overcast, 10°C · sun recommended',
    })
  })

  it('is balanced in mild weather', () => {
    expect(weatherAdvice({ temperature: 18, cloudCover: 40 })).toEqual({
      title: 'A balanced route',
      sub: '18°C · balanced conditions',
    })
  })

  it('derives the chip condition from cloud cover', () => {
    expect(weatherCondition({ temperature: 26, cloudCover: 20 })).toBe('Sunny')
    expect(weatherCondition({ temperature: 26, cloudCover: 70 })).toBe('Overcast')
  })
})

describe('shade and quiet labels', () => {
  it('maps the three shade values', () => {
    expect(shadeLabel('hot')).toBe('More shade')
    expect(shadeLabel('balanced')).toBe('Balanced')
    expect(shadeLabel('cloudy')).toBe('More sun')
  })

  it('shows Quieter only when the preference is on', () => {
    expect(quieterVisible(true)).toBe(true)
    expect(quieterVisible(false)).toBe(false)
  })
})
