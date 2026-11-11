from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from speedlimit.config import load_config
from speedlimit.features import FEATURES
from speedlimit.model import (ModelArtefact, baseline_predict, baseline_table, evaluate, load,
                              predict_rate, save, split_by_day, train)

ROOT = Path(__file__).resolve().parents[2]
CFG = load_config(ROOT / "config.yaml")


def _synthetic(n_days=31, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.MultiIndex.from_product([range(1, n_days + 1), range(24)], names=["day", "hour"])
    X = pd.DataFrame(rng.normal(size=(len(idx), len(FEATURES))), index=idx, columns=FEATURES)
    X["speed_limit"] = rng.choice([40, 50, 60, 70, 80], size=len(idx)).astype(float)
    lam = np.exp(0.2 + 0.3 * X["temp"].clip(-2, 2))
    y = pd.Series(rng.poisson(lam), index=idx, name="near_accidents")
    return X, y


@pytest.fixture(scope="module")
def fitted():
    X, y = _synthetic()
    return train(X, y, CFG.model), X, y


def test_split_by_day():
    X, _ = _synthetic()
    tr, te = split_by_day(X, CFG.split)
    tr_days = set(tr.index.get_level_values("day"))
    te_days = set(te.index.get_level_values("day"))
    assert tr_days == set(range(1, 25)) and te_days == set(range(25, 32))
    assert not tr_days & te_days


def test_ensemble_size_and_features(fitted):
    art, _, _ = fitted
    assert isinstance(art, ModelArtefact)
    assert len(art.estimators) == len(CFG.model.seeds) == 5
    assert art.features == FEATURES


def test_rates_non_negative(fitted):
    art, X, _ = fitted
    assert (predict_rate(art, X) >= 0).all()


def test_smearing_matches_train_mean(fitted):
    """k corrects the log1p back-transform bias: mean prediction ~ mean target."""
    art, X, y = fitted
    assert predict_rate(art, X).mean() == pytest.approx(y.mean(), rel=0.02)
    assert art.smearing_k > 0


def test_reproducible(fitted):
    art, X, y = fitted
    again = train(X, y, CFG.model)
    np.testing.assert_array_equal(predict_rate(art, X), predict_rate(again, X))


def test_roundtrip(fitted, tmp_path):
    art, X, _ = fitted
    p = tmp_path / "m.joblib"
    save(art, p)
    np.testing.assert_array_equal(predict_rate(load(p), X), predict_rate(art, X))


def test_load_rejects_feature_mismatch(fitted, tmp_path):
    import dataclasses
    art, _, _ = fitted
    bad = dataclasses.replace(art, features=FEATURES[::-1])
    p = tmp_path / "bad.joblib"
    save(bad, p)
    with pytest.raises(ValueError, match="feature"):
        load(p)


def test_baseline_table_and_fallback():
    h = pd.DataFrame({"condition": ["dark", "dark", "normal", "normal"],
                      "speed_limit": [60, 60, 80, 80], "near_accidents": [1, 3, 0, 2]})
    t = baseline_table(h)
    assert t[("dark", 60)] == 2.0 and t[("normal", 80)] == 1.0
    pred = baseline_predict(t, ["dark", "dark", "black_ice"], [60, 40, 50])
    assert pred[0] == 2.0
    assert pred[1] == 2.0      # unseen limit -> condition mean
    assert pred[2] == 1.5      # unseen condition -> global mean


def test_evaluate_reports_required_metrics(fitted):
    art, X, y = fitted
    m = evaluate(predict_rate(art, X), y.to_numpy(), np.full(len(y), y.mean()))
    for k in ("mae", "rmse", "poisson_dev", "mae_baseline", "poisson_dev_baseline", "skill", "sum_ratio",
              "calibration"):
        assert k in m
    assert len(m["calibration"]) == 5
