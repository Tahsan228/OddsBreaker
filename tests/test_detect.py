from oddsbreaker.detect import (default_detect, is_shiny_score, make_ref, matching_refs, score_frame,
                                suggest_threshold, usable_refs)
from oddsbreaker.system import StubPlatform


def setup_det():
    plat = StubPlatform()
    normal = plat.capture(150, 70, 60, 60)
    plat.shiny = True
    shiny = plat.capture(150, 70, 60, 60)
    det = default_detect()
    det["region"] = [110, 30, 60, 60]
    det["refs"] = [make_ref(normal)]
    return det, normal, shiny


def test_compare_mode():
    det, normal, shiny = setup_det()
    refs = usable_refs(det)
    s0, s1 = score_frame(normal, det, refs), score_frame(shiny, det, refs)
    assert s0 == 0 and s1 > 15
    assert not is_shiny_score(det, s0) and is_shiny_score(det, s1)


def test_refs_must_match_the_area():
    det, _n, _s = setup_det()
    assert len(matching_refs(det)) == 1
    det["region"] = [0, 0, 50, 50]
    assert matching_refs(det) == [] and usable_refs(det) == []


def test_color_mode():
    det, normal, shiny = setup_det()
    det["mode"] = "color"
    det["colors"] = [list(shiny.pixel(50, 22))]
    assert score_frame(shiny, det, []) > 10 and score_frame(normal, det, []) == 0


def test_suggest_threshold():
    det = default_detect()
    assert suggest_threshold(det, [1, 2]) is None
    s = suggest_threshold(det, [0.0, 1.0, 2.5, 3.0, 4.0, 0.5])
    assert 5.0 <= s <= 60.0 and s > 4.0
