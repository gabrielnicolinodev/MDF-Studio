import math

import pytest

from app.core.box_geometry import build_box_geometry
from app.core.box_parameters import BoxParameters, BoxType
from app.core.validation import GeometryError, has_errors, parse_number, validate_parameters


@pytest.mark.parametrize("field", ["width", "depth", "height", "thickness"])
@pytest.mark.parametrize("bad", [0, -1, -0.001, float("nan"), float("inf"), float("-inf")])
def test_non_positive_or_non_finite_dimensions_rejected(field, bad):
    issues = validate_parameters(BoxParameters(**{field: bad}))
    assert has_errors(issues)
    assert any(i.field == field for i in issues)
    with pytest.raises(GeometryError):
        build_box_geometry(BoxParameters(**{field: bad}))


@pytest.mark.parametrize("field,bad", [("width", 5000), ("thickness", 40), ("width", 1),
                                       ("clearance", 3), ("kerf", 2), ("clearance", -0.1)])
def test_out_of_range_rejected(field, bad):
    assert has_errors(validate_parameters(BoxParameters(**{field: bad})))


@pytest.mark.parametrize("count", [2, 4, 6, 1, 101, True, 3.5])
def test_invalid_finger_count_rejected(count):
    assert has_errors(validate_parameters(BoxParameters(finger_count=count)))


@pytest.mark.parametrize("count", [None, 3, 5, 9, 99])
def test_valid_finger_count_accepted(count):
    assert not has_errors(validate_parameters(BoxParameters(finger_count=count)))


def test_default_parameters_are_valid():
    assert validate_parameters(BoxParameters()) == []


def test_error_messages_are_in_portuguese_and_name_the_field():
    issues = validate_parameters(BoxParameters(width=-5))
    assert "Largura" in issues[0].message


@pytest.mark.parametrize("text,expected", [("100", 100.0), (" 12,5 ", 12.5), ("3.2", 3.2)])
def test_parse_number(text, expected):
    assert parse_number(text) == expected


@pytest.mark.parametrize("text", ["", "abc", "1,2.3"])
def test_parse_number_rejects_garbage(text):
    with pytest.raises(ValueError):
        parse_number(text)


def test_parse_number_passes_nan_for_core_to_reject():
    assert math.isnan(parse_number("nan"))
    assert has_errors(validate_parameters(BoxParameters(width=parse_number("nan"))))


@pytest.mark.parametrize("kwargs", [
    dict(width=10, depth=10, height=10, thickness=3),     # vão interno insuficiente
    dict(width=12, thickness=5),                          # junta curta demais
    dict(height=9, thickness=4, box_type=BoxType.CLOSED), # altura incompatível
    dict(finger_count=99),                                # dedos estreitos demais
    dict(clearance=1.0, kerf=0.6, width=20, depth=20, height=20),  # folga+kerf excessivos
])
def test_incompatible_geometry_is_rejected_with_message(kwargs):
    with pytest.raises(GeometryError) as exc:
        build_box_geometry(BoxParameters(**kwargs))
    assert len(str(exc.value)) > 20
