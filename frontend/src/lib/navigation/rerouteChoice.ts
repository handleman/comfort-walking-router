function remainingScore(route: RouteForChoice): number {
  let total = 0
  let weighted = 0
  for (const seg of route.profile) {
    const weight = seg.to_m - Math.max(seg.from_m, route.from_m)
    if (weight <= 0) continue
    weighted += seg.score * weight
    total += weight
  }
  return total === 0 ? 0 : weighted / total
}

export interface RouteForChoice {
  profile: ReadonlyArray<{ from_m: number; to_m: number; score: number }>
  distance_m: number
  from_m: number
}

export type RerouteVerdict = 'replace' | 'ask' | 'keep'

export interface RerouteChoice {
  delta: number
  remainingKm: number
  verdict: RerouteVerdict
  summary: string
}

export function compareReroutes(current: RouteForChoice, candidate: RouteForChoice): RerouteChoice {
  const remainingKm =
    Math.round((Math.max(0, candidate.distance_m - candidate.from_m) / 1000) * 10) / 10
  const delta =
    remainingKm === 0
      ? 0
      : Math.round((remainingScore(candidate) - remainingScore(current)) * 10) / 10
  const verdict: RerouteVerdict =
    remainingKm === 0 ? 'ask' : delta >= 5 ? 'replace' : delta <= -5 ? 'keep' : 'ask'
  const deltaText = delta < 0 ? `−${Math.abs(delta)}` : `+${delta}`
  const summary =
    `${deltaText} comfort · ${remainingKm} km left` +
    (verdict === 'keep' ? ' · current route is shadier' : '')
  return { delta, remainingKm, verdict, summary }
}
