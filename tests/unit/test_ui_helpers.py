"""Review I-4: the light slider must round-trip lux exactly (no +0.001 lux drift across SPEC1)."""
import pytest

from speedlimit.ui_helpers import lux_to_slider, slider_to_lux


@pytest.mark.parametrize("lux", [0.4995, 0.499, 0.5, 2.0, 25000.0, 0.01])
def test_light_slider_round_trip(lux):
    assert slider_to_lux(lux_to_slider(lux)) == pytest.approx(lux, rel=1e-9)


def test_dark_sample_stays_dark():
    assert slider_to_lux(lux_to_slider(0.4995)) < 0.5


def test_zero_lux_maps_to_slider_floor():
    assert lux_to_slider(0.0) == -3.0 and slider_to_lux(-3.0) == pytest.approx(0.001)
