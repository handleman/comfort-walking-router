"""T1 AC-1: profile() cut points, coverage and determinism."""

from app.comfort import PROFILE_SEGMENT_M, ProfileSegment, profile

GEO = {"type": "LineString", "coordinates": [[13.40, 52.52], [13.42, 52.52]]}
FACTORS = {"shade_factor": 0.8, "quiet_factor": 0.5, "lit_share": 0.5}


def test_profile_cut_points_and_full_coverage():
    segs = profile(GEO, FACTORS)
    assert isinstance(segs, list) and segs
    assert all(isinstance(s, ProfileSegment) for s in segs)
    assert segs[0].from_m == 0.0
    prev = 0.0
    for s in segs:
        assert s.from_m == prev
        assert s.to_m - s.from_m <= PROFILE_SEGMENT_M
        prev = s.to_m
    total = sum(s.to_m - s.from_m for s in segs)
    assert abs(segs[-1].to_m - total) <= 1.0
    assert 1300.0 <= total <= 1500.0  # ~1400 m for a 0.02° run at 52.52°N
    assert profile(GEO, FACTORS) == segs


def test_profile_score_weights_and_clamps():
    # Plan weights: base 50, +20·shade, +15·quiet − 15·(1−quiet); lit is
    # unmeasured and contributes 0.
    all_on = profile(GEO, {"shade_factor": 1.0, "quiet_factor": 1.0})
    assert all(s.score == 85.0 for s in all_on)
    assert all(s.factor == "shade" for s in all_on)

    all_off = profile(GEO, {"shade_factor": 0.0, "quiet_factor": 0.0})
    assert all(s.score == 35.0 for s in all_off)
    # Nothing moved the score, so the ambient-conditions factor is named.
    assert all(s.factor == "traffic" for s in all_off)

    # All-None factors exercise the no-OSM-data branch without contradicting
    # the None-on-{} requirement (see none_on_missing).
    no_data = profile(GEO, {"shade_factor": None, "quiet_factor": None, "lit_share": None})
    assert no_data is not None
    assert all(s.score == 50.0 and s.factor == "unknown" for s in no_data)

    empty = profile(GEO, {})
    assert empty is None  # no factors at all -> no profile (see none_on_missing)


def test_profile_factor_choice_and_labels():
    shade_dom = profile(GEO, {"shade_factor": 1.0, "quiet_factor": 0.2, "lit_share": 0.2})
    quiet_dom = profile(GEO, {"shade_factor": 0.2, "quiet_factor": 1.0, "lit_share": 0.2})
    lit_dom = profile(GEO, {"shade_factor": 0.2, "quiet_factor": 0.2, "lit_share": 1.0})
    assert all(s.factor == "shade" for s in shade_dom)
    assert all(s.factor == "quiet" for s in quiet_dom)
    assert all(s.factor == "lit" for s in lit_dom)
    for segs in (shade_dom, quiet_dom, lit_dom):
        for s in segs:
            assert isinstance(s.label, str) and 0 < len(s.label) <= 40


def test_weighted_score_empty():
    from app.comfort import weighted_score
    assert weighted_score([]) == 0.0


def test_weighted_score_matches_length_weighted_mean():
    from app.comfort import weighted_score
    segs = profile(GEO, FACTORS)
    ws = weighted_score(segs)
    assert isinstance(ws, float) and 0.0 <= ws <= 100.0
    total = sum(s.to_m - s.from_m for s in segs)
    expected = sum(s.score * (s.to_m - s.from_m) for s in segs) / total
    assert abs(ws - expected) < 1e-9


def test_profile_none_on_missing_factors_or_geometry():
    assert profile(GEO, None) is None
    assert profile(GEO, {}) is None
    assert profile({"type": "LineString", "coordinates": []}, FACTORS) is None
