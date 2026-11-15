import { describe, expect, it } from 'vitest'
import { compareReroutes } from './rerouteChoice'

describe('compareReroutes', () => {
  it('weights by remaining distance: an already-walked bad stretch does not dominate', () => {
    const current = {
      // walked bad stretch (to_m <= from_m of route) is excluded by weighting
      profile: [
        { from_m: 0, to_m: 500, score: 10 },
        { from_m: 500, to_m: 1000, score: 50 },
      ],
      distance_m: 1000,
      from_m: 500,
    }
    const candidate = {
      profile: [
        { from_m: 0, to_m: 500, score: 60 },
        { from_m: 500, to_m: 1000, score: 60 },
      ],
      distance_m: 1000,
      from_m: 500,
    }
    const choice = compareReroutes(current, candidate)
    expect(choice.delta).toBe(10)
  })

  it('returns replace at the +5 threshold', () => {
    const current = {
      profile: [{ from_m: 0, to_m: 1000, score: 50 }],
      distance_m: 1000,
      from_m: 0,
    }
    const candidate = {
      profile: [{ from_m: 0, to_m: 1000, score: 55 }],
      distance_m: 1000,
      from_m: 0,
    }
    const choice = compareReroutes(current, candidate)
    expect(choice.delta).toBe(5)
    expect(choice.verdict).toBe('replace')
    expect(choice.summary).toContain('+5')
    expect(choice.summary).toContain('km left')
  })

  it('returns keep at the −5 threshold', () => {
    const current = {
      profile: [{ from_m: 0, to_m: 1000, score: 55 }],
      distance_m: 1000,
      from_m: 0,
    }
    const candidate = {
      profile: [{ from_m: 0, to_m: 1000, score: 50 }],
      distance_m: 1000,
      from_m: 0,
    }
    const choice = compareReroutes(current, candidate)
    expect(choice.delta).toBe(-5)
    expect(choice.verdict).toBe('keep')
    expect(choice.summary).toContain('−5')
    expect(choice.summary).toContain('km left')
  })

  it('returns ask just below the threshold (+4.9) and at zero delta', () => {
    const base = {
      profile: [{ from_m: 0, to_m: 1000, score: 50 }],
      distance_m: 1000,
      from_m: 0,
    }
    const justBelow = compareReroutes(base, {
      profile: [{ from_m: 0, to_m: 1000, score: 54.9 }],
      distance_m: 1000,
      from_m: 0,
    })
    expect(justBelow.delta).toBe(4.9)
    expect(justBelow.verdict).toBe('ask')
    expect(justBelow.summary).toContain('+4.9')
    expect(justBelow.summary).toContain('km left')

    const zero = compareReroutes(base, {
      profile: [{ from_m: 0, to_m: 1000, score: 50 }],
      distance_m: 1000,
      from_m: 0,
    })
    expect(zero.delta).toBe(0)
    expect(zero.verdict).toBe('ask')
    expect(zero.summary).toContain('+0')
    expect(zero.summary).toContain('km left')
  })

  it('clips mid-segment from_m overlap when weighting', () => {
    const current = {
      profile: [
        { from_m: 0, to_m: 200, score: 20 },
        { from_m: 200, to_m: 1000, score: 80 },
      ],
      distance_m: 1000,
      from_m: 100,
    }
    const candidate = {
      profile: [{ from_m: 0, to_m: 1000, score: 80 }],
      distance_m: 1000,
      from_m: 100,
    }
    const choice = compareReroutes(current, candidate)
    // current remaining: (20*100 + 80*800) / 900 = 73.333…; candidate: 80
    expect(choice.delta).toBe(6.7)
    expect(choice.remainingKm).toBe(0.9)
    expect(choice.verdict).toBe('replace')
  })

  it('returns 0/0/ask when candidate.from_m is past the end', () => {
    const current = {
      profile: [{ from_m: 0, to_m: 1000, score: 50 }],
      distance_m: 1000,
      from_m: 0,
    }
    const candidate = {
      profile: [{ from_m: 0, to_m: 1000, score: 90 }],
      distance_m: 1000,
      from_m: 1000,
    }
    const choice = compareReroutes(current, candidate)
    expect(choice.remainingKm).toBe(0)
    expect(choice.delta).toBe(0)
    expect(choice.verdict).toBe('ask')
  })
})
