import time

import pytest

from app.core.box_parameters import BoxParameters, BoxType, DimensionMode
from app.core.layout import LayoutParameters
from app.core.validation import Severity
from app.generators.box_generator import BoxGenerator


def test_valid_project_is_ok_and_summarized():
    r = BoxGenerator().generate(BoxParameters())
    assert r.ok and r.geometry and r.layout
    s = BoxGenerator.summarize(r)
    assert s.external == (100.0, 80.0, 50.0)
    assert s.internal == (94.0, 74.0, 44.0)
    assert len(s.panels) == 6 and len(s.joints) == 12
    assert s.kerf_active is False
    assert s.panels_area < s.bbox_area


@pytest.mark.parametrize("params", [
    BoxParameters(width=float("nan")), BoxParameters(height=0), BoxParameters(width=12, thickness=5),
    BoxParameters(finger_count=4),
])
def test_invalid_projects_return_errors_without_raising(params):
    r = BoxGenerator().generate(params)
    assert not r.ok and r.geometry is None and r.layout is None
    assert r.issues and r.issues[0].severity is Severity.ERROR
    with pytest.raises(ValueError):
        BoxGenerator.summarize(r)


def test_workspace_overflow_makes_result_not_ok_but_keeps_geometry():
    r = BoxGenerator().generate(BoxParameters(), LayoutParameters(workspace_width=100, workspace_height=100))
    assert not r.ok and r.geometry is not None


def test_internal_mode_summary_matches_request():
    p = BoxParameters(width=100, depth=80, height=40, dimension_mode=DimensionMode.INTERNAL,
                      box_type=BoxType.OPEN)
    s = BoxGenerator.summarize(BoxGenerator().generate(p, LayoutParameters(workspace_width=600, workspace_height=600)))
    assert s.internal == (100, 80, 37 + 3)  # aberta: altura interna pedida = 40
    assert s.external == (106, 86, 43)
    assert len(s.panels) == 5


def test_normal_calculation_is_fast_enough_not_to_freeze_the_ui():
    t0 = time.perf_counter()
    for _ in range(5):
        assert BoxGenerator().generate(BoxParameters(width=400, depth=300, height=200,
                                                     thickness=6, finger_count=21),
                                       LayoutParameters(workspace_width=2000, workspace_height=2000)).ok
    assert (time.perf_counter() - t0) / 5 < 0.5
