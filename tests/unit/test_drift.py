"""Retraining check year N vs N+1 (D13, slide 19)."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from speedlimit import drift
from speedlimit.config import load_config
from speedlimit.features import FEATURES

ROOT = Path(__file__).resolve().parents[2]
CFG = load_config(ROOT / "config.yaml")


def _features(seed=0, n_days=31):
    rng = np.random.default_rng(seed)
    idx = pd.MultiIndex.from_product([range(1, n_days + 1), range(24)], names=["day", "hour"])
    X = pd.DataFrame(rng.normal(size=(len(idx), len(FEATURES))), index=idx, columns=FEATURES)
    X["temp"] = rng.normal(-3.5, 7.4, len(idx))
    X["speed_limit"] = rng.choice([40, 50, 60, 70, 80], len(idx)).astype(float)
    return X


def test_identical_no_retrain():
    X = _features()
    rep = drift.drift_report(X, X.copy(), FEATURES, CFG.drift)
    assert drift.verdict(rep) == "no_retrain"
    assert not rep.per_feature.drift.any()
    assert (rep.per_feature.ks_stat == 0).all()


def test_temp_shift_retrain():
    X = _features()
    Y = X.copy()
    Y["temp"] = Y["temp"] + 8.0
    rep = drift.drift_report(X, Y, FEATURES, CFG.drift)
    assert drift.verdict(rep) == "retrain"
    assert rep.per_feature.loc["temp", "drift"]
    assert rep.per_feature.drift.sum() == 1
    assert "temp" in rep.reason


def test_small_shift_is_not_drift():
    """A shift below 0.5 std is noise, even if KS notices it on many rows."""
    X = _features()
    Y = X.copy()
    Y["temp"] = Y["temp"] + 1.0               # 1 degC on std 7.4 ~ 0.14 std
    rep = drift.drift_report(X, Y, FEATURES, CFG.drift)
    assert drift.verdict(rep) == "no_retrain"


def test_non_core_drift_does_not_force_retrain():
    X = _features()
    Y = X.copy()
    Y["noise"] = Y["noise"] + 5.0
    rep = drift.drift_report(X, Y, FEATURES, CFG.drift)
    assert rep.per_feature.loc["noise", "drift"]
    assert drift.verdict(rep) == "no_retrain"


def test_identity_check_flags_duplicate_dataset():
    raw = pd.DataFrame({"day": [1, 1], "hour": [0, 1], "sensor": [1, 2], "value": [0.0, 1.5]})
    X = _features()
    rep = drift.drift_report(X, X, FEATURES, CFG.drift, ref_raw=raw, new_raw=raw.copy())
    assert rep.identical_rows == 2 and rep.duplicate_dataset
    assert "identical" in rep.reason.lower()


@pytest.mark.realdata
def test_real_year_n1(tmp_path):
    rc = drift.main(["--config", str(ROOT / "config.yaml"), "--reports-dir", str(tmp_path),
                     "--evidence", str(tmp_path / "drift_report.md")])
    assert rc == 0
    import json
    rep = json.loads((tmp_path / "drift_report.json").read_text())
    assert rep["verdict"] == "no_retrain"
    assert rep["identical_rows"] == 12648 and rep["duplicate_dataset"] is True
    assert "no_retrain" in (tmp_path / "drift_report.md").read_text(encoding="utf-8")
