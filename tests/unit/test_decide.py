"""REQ1 decision: candidate sweep, monotone guard (D9), epsilon rule (D25), reduce-only (D33)."""
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from speedlimit.config import load_config
from speedlimit.decide import req1_limit
from speedlimit.domain import RuleResult, Situation
from speedlimit.features import FEATURES
from speedlimit.model import ModelArtefact, monotone_guard

ROOT = Path(__file__).resolve().parents[2]
CFG = load_config(ROOT / "config.yaml")
DARK = RuleResult(dark=True, black_ice=False)


class _Stub:
    """Estimator stub: returns a fixed rate per speed limit (feature column)."""

    def __init__(self, rates):
        self.rates = rates

    def predict(self, X):
        return np.array([self.rates[int(v)] for v in X["speed_limit"]], dtype=float)


def _art(rates, cells=None):
    return ModelArtefact(estimators=[_Stub(rates)], smearing_k=1.0, features=list(FEATURES),
                         cell_counts=cells or {})


def _sit(**kw):
    base = dict(timestamp=datetime(2026, 1, 6, 20), lux=0.08, water_um=0.0, temp_c=-4.8, humidity=85.0,
                noise_db=90.0, wind_strength=10.0, wind_dir_deg=180.0, traffic_cps=12.0, current_limit=60)
    base.update(kw)
    return Situation(**base)


# --- monotone guard (D9) ---------------------------------------------------------

def test_monotone_guard():
    g = monotone_guard({40: 1.8, 50: 1.4, 60: 1.2, 70: 1.1, 80: 1.3})
    assert g[40] <= g[50] <= g[60] <= g[70] <= g[80]
    assert g == {40: 1.1, 50: 1.1, 60: 1.1, 70: 1.1, 80: 1.3}


def test_monotone_guard_keeps_monotone_input():
    r = {40: 0.5, 50: 0.7, 60: 0.9, 70: 1.1, 80: 1.4}
    assert monotone_guard(r) == r


# --- selection (D7, D25, D33) -------------------------------------------------------

def test_picks_highest_meeting_target():
    r = req1_limit(_sit(), _art({40: .5, 50: .7, 60: .9, 70: 1.1, 80: 1.4}), CFG, rule=DARK)
    assert (r.limit, r.target_reachable, r.source, r.active) == (60, True, "model", True)


def test_none_reachable_epsilon():
    r = req1_limit(_sit(), _art({40: 1.20, 50: 1.22, 60: 1.24, 70: 1.30, 80: 1.40}), CFG, rule=DARK)
    assert (r.limit, r.target_reachable) == (60, False)


def test_none_reachable_unique_minimum_gives_40():
    r = req1_limit(_sit(), _art({40: 1.20, 50: 1.30, 60: 1.40, 70: 1.50, 80: 1.60}), CFG, rule=DARK)
    assert (r.limit, r.target_reachable) == (40, False)


def test_never_80_when_req1_active():
    """D33: REQ1 must reduce, even when the model rates 80 km/h safe."""
    r = req1_limit(_sit(), _art({40: .5, 50: .5, 60: .5, 70: .5, 80: .5}), CFG, rule=DARK)
    assert r.limit == 70 and r.target_reachable


def test_confounded_curve_does_not_keep_80():
    """Raw curve 'faster is safer' (F04): guard flattens it; result must still be a reduction."""
    r = req1_limit(_sit(), _art({40: 1.8, 50: 1.5, 60: 1.3, 70: 1.2, 80: 1.1}), CFG, rule=DARK)
    assert r.limit <= 70
    assert r.rates_guarded[40] <= r.rates_guarded[70]
    assert r.rates_raw[40] == 1.8


def test_rates_reported_for_all_candidates():
    r = req1_limit(_sit(), _art({40: .5, 50: .7, 60: .9, 70: 1.1, 80: 1.4}), CFG, rule=DARK)
    assert set(r.rates_raw) == set(r.rates_guarded) == {40, 50, 60, 70, 80}


def test_extrapolated_cells_flagged():
    cells = {("dark", 40): 7, ("dark", 50): 51, ("dark", 60): 211, ("dark", 70): 85, ("dark", 80): 0}
    r = req1_limit(_sit(), _art({40: .5, 50: .7, 60: .9, 70: 1.1, 80: 1.4}, cells), CFG, rule=DARK)
    assert r.extrapolated == (80,)


# --- activation and fallbacks ---------------------------------------------------------

def test_inactive_when_no_condition():
    r = req1_limit(_sit(lux=50000.0), _art({l: 2.0 for l in (40, 50, 60, 70, 80)}), CFG,
                   rule=RuleResult(dark=False, black_ice=False))
    assert (r.active, r.limit, r.source) == (False, 80, "inactive")


def test_rule_evaluated_when_not_given():
    r = req1_limit(_sit(), _art({40: .5, 50: .7, 60: .9, 70: 1.1, 80: 1.4}), CFG)
    assert r.active and r.limit == 60


def test_missing_artefact_uses_baseline_table():
    table = {("dark", 40): 1.86, ("dark", 50): 1.45, ("dark", 60): 1.27, ("dark", 70): 1.13,
             ("dark", "*"): 1.3, ("*", "*"): 1.3}
    r = req1_limit(_sit(), None, CFG, rule=DARK, baseline=table)
    assert r.source == "baseline_table"
    assert r.limit == 70 and not r.target_reachable


def test_missing_artefact_and_baseline_raises():
    with pytest.raises(ValueError):
        req1_limit(_sit(), None, CFG, rule=DARK)
