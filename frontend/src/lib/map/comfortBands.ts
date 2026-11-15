export type ComfortBand = 'good' | 'mixed' | 'poor'

export interface ComfortProfileSegment {
  from_m: number
  to_m: number
  score: number
  factor: 'shade' | 'sun' | 'quiet' | 'traffic' | 'lit' | 'unknown'
  label: string
}

export interface ComfortBandRun {
  band: ComfortBand
  from_m: number
  to_m: number
  score: number
  label: string
}

export const COMFORT_BANDS: { band: ComfortBand; colour: string; range: string }[] = [
  { band: 'good', colour: '#2f855a', range: '70–100' },
  { band: 'mixed', colour: '#d69e2e', range: '40–70' },
  { band: 'poor', colour: '#c53030', range: '0–40' },
]

export function bandForScore(score: number): ComfortBand {
  if (score >= 70) return 'good'
  if (score >= 40) return 'mixed'
  return 'poor'
}

export const COMFORT_UNAVAILABLE_TEXT = 'Comfort profile unavailable (no OSM data).'

export function bandColour(band: ComfortBand): string {
  const entry = COMFORT_BANDS.find((b) => b.band === band)
  return entry ? entry.colour : '#888888'
}

export function mergeBandRuns(segments: ComfortProfileSegment[]): ComfortBandRun[] {
  const runs: ComfortBandRun[] = []
  for (const segment of segments) {
    const band = bandForScore(segment.score)
    const last = runs[runs.length - 1]
    if (last && last.band === band) {
      last.to_m = segment.to_m
      last.score = Math.max(last.score, Math.round(segment.score))
      if (Math.round(segment.score) >= last.score) last.label = segment.label
    } else {
      runs.push({
        band,
        from_m: segment.from_m,
        to_m: segment.to_m,
        score: Math.round(segment.score),
        label: segment.label,
      })
    }
  }
  return runs
}

export function formatRun(run: ComfortBandRun): string {
  return `${run.label} · ${run.from_m}–${run.to_m} m · ${run.score}/100`
}
