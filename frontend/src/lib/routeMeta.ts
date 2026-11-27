/** Pure derivations shared by the 041 comfort surfaces. */

import type { ComfortProfileSegment } from './map/comfortBands'

export type ShadePreference = 'hot' | 'cloudy' | 'balanced'

export interface Weather {
  temperature: number
  cloudCover: number
}

export function shadeLabel(preference: string | null | undefined): string {
  if (preference === 'hot') return 'More shade'
  if (preference === 'cloudy') return 'More sun'
  return 'Balanced'
}

/** Shaded share of the covered distance, rounded; null without a profile. */
export function shadedPercent(profile: ComfortProfileSegment[] | null | undefined): number | null {
  if (!profile || profile.length === 0) return null
  let covered = 0
  let shaded = 0
  for (const segment of profile) {
    const length = segment.to_m - segment.from_m
    if (!(length > 0)) continue
    covered += length
    if (segment.factor === 'shade') shaded += length
  }
  if (covered <= 0) return null
  return Math.round((shaded / covered) * 100)
}

export function weatherCondition(weather: Weather): 'Sunny' | 'Overcast' {
  return weather.cloudCover >= 70 ? 'Overcast' : 'Sunny'
}

export interface WeatherAdvice {
  title: string
  sub: string
}

export function weatherAdvice(weather: Weather): WeatherAdvice {
  const temperature = Math.round(weather.temperature)
  if (weather.temperature >= 25 && weather.cloudCover < 70) {
    return {
      title: 'A little shade goes a long way',
      sub: `Sunny, ${temperature}°C · shade recommended`,
    }
  }
  if (weather.cloudCover >= 70) {
    return {
      title: 'A brighter route feels better',
      sub: `Overcast, ${temperature}°C · sun recommended`,
    }
  }
  return {
    title: 'A balanced route',
    sub: `${temperature}°C · balanced conditions`,
  }
}

export function quieterVisible(avoidTraffic: boolean): boolean {
  return avoidTraffic
}
