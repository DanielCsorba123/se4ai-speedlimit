from datetime import datetime
from pathlib import Path

import math
import pandas as pd
import pytest

from speedlimit.config import load_config
from speedlimit.domain import Situation
from speedlimit.rules import evaluate, is_black_ice, is_dark, label_conditions

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def rcfg():
    return load_config(ROOT / "config.yaml").rules


def _sit(**kw):
    base = dict(timestamp=datetime(2026, 1, 6, 12), lux=50000.0, water_um=0.0, temp_c=5.0, humidity=80.0,
                noise_db=90.0, wind_strength=10.0, wind_dir_deg=90.0, traffic_cps=10.0, current_limit=80)
    base.update(kw)
    return Situation(**base)


def test_dark_boundary(rcfg):
    assert is_dark(0.499, rcfg) is True
    assert is_dark(0.5, rcfg) is False
    assert is_dark(0.501, rcfg) is False


def test_ice_boundary(rcfg):
    assert is_black_ice(1001, -0.1, rcfg) is True
    assert is_black_ice(1000, -5, rcfg) is False
    assert is_black_ice(1500, 0, rcfg) is False


def test_evaluate_daylight_dry_is_no_reason(rcfg):
    r = evaluate(_sit(), rcfg)
    assert not r.dark and not r.black_ice and not r.req1_active


def test_evaluate_dark_and_ice(rcfg):
    r = evaluate(_sit(lux=0.1, water_um=1200, temp_c=-2), rcfg)
    assert r.dark and r.black_ice


def test_missing_input_is_fail_safe(rcfg):
    r = evaluate(_sit(lux=math.nan), rcfg)
    assert r.dark and r.missing_inputs == ("lux",)
    r2 = evaluate(_sit(temp_c=math.nan), rcfg)
    assert r2.black_ice and "temp_c" in r2.missing_inputs


def test_label_conditions_precedence(rcfg):
    h = pd.DataFrame({"lux": [0.1, 100.0, 100.0, 100.0], "water": [2000, 2000, 0, 0],
                      "temp": [-3, -3, 5, 5], "speed_limit": [60, 70, 80, 60]},
                     index=pd.MultiIndex.from_tuples([(1, 0), (1, 1), (1, 2), (1, 3)], names=["day", "hour"]))
    out = label_conditions(h, rcfg)
    assert out.condition.tolist() == ["dark", "black_ice", "normal", "normal"]
    assert out.unexplained_reduction.tolist() == [False, False, False, True]
