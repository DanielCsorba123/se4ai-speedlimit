"""Near-accident rate model (SPEC3, D7): 5-seed MLP ensemble on log1p counts.

Architecture §5.2: StandardScaler + MLPRegressor inside a
TransformedTargetRegressor(log1p/expm1), averaged over seeds, back-transform
bias corrected by a smearing factor k so predicted *rates* are not biased low.
"""
from __future__ import annotations

import dataclasses
import platform
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from collections.abc import Mapping
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import TransformedTargetRegressor
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import mean_absolute_error, mean_poisson_deviance, mean_squared_error
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from speedlimit.config import ModelConfig, SplitConfig
from speedlimit.features import FEATURES


@dataclass(frozen=True)
class ModelArtefact:
    estimators: list[Any]
    smearing_k: float
    features: list[str]
    version: str = "unversioned"
    candidate_limits: list[int] = field(default_factory=lambda: [40, 50, 60, 70, 80])
    baseline_table: dict[tuple[str, int], float] = field(default_factory=dict)
    cell_counts: dict[tuple[str, int], int] = field(default_factory=dict)
    train_days: list[int] = field(default_factory=list)
    test_days: list[int] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    data_hash: str = ""
    lib_versions: dict[str, str] = field(default_factory=dict)
    config_snapshot: dict[str, Any] = field(default_factory=dict)


def _days(rng: list[int]) -> list[int]:
    return list(range(rng[0], rng[1] + 1))


def split_by_day(frame: pd.DataFrame, cfg: SplitConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    """D12: whole days go to train or test, never single hours."""
    day = frame.index.get_level_values("day")
    return frame[day.isin(_days(cfg.train_days))], frame[day.isin(_days(cfg.test_days))]


def _make_estimator(cfg: ModelConfig, seed: int):
    mlp = MLPRegressor(hidden_layer_sizes=tuple(cfg.hidden_layer_sizes), activation="relu", solver="adam",
                       alpha=cfg.alpha, learning_rate_init=cfg.learning_rate_init, batch_size=32,
                       max_iter=cfg.max_iter, early_stopping=True, validation_fraction=0.15,
                       n_iter_no_change=50, random_state=seed)
    pipe = Pipeline([("scale", StandardScaler()), ("mlp", mlp)])
    if cfg.target_transform == "log1p":
        return TransformedTargetRegressor(regressor=pipe, func=np.log1p, inverse_func=np.expm1, check_inverse=False)
    return pipe


def _raw_mean(estimators, X: pd.DataFrame) -> np.ndarray:
    return np.mean([e.predict(X[FEATURES]) for e in estimators], axis=0)


def train(X: pd.DataFrame, y: pd.Series, cfg: ModelConfig) -> ModelArtefact:
    X = X[FEATURES]
    estimators = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        for seed in cfg.seeds:
            estimators.append(_make_estimator(cfg, seed).fit(X, np.asarray(y, dtype=float)))
    raw = np.clip(_raw_mean(estimators, X), 0, None)
    k = float(np.mean(y) / raw.mean()) if raw.mean() > 0 else 1.0
    return ModelArtefact(
        estimators=estimators, smearing_k=k, features=list(FEATURES),
        lib_versions={"python": platform.python_version(), "sklearn": sklearn.__version__,
                      "pandas": pd.__version__, "numpy": np.__version__},
        config_snapshot=dataclasses.asdict(cfg) | {"artefact": str(cfg.artefact)},
    )


def predict_rate(art: ModelArtefact, X: pd.DataFrame) -> np.ndarray:
    """Predicted near-accidents per hour (>= 0, smearing-corrected)."""
    return np.clip(art.smearing_k * _raw_mean(art.estimators, X), 0, None)


def save(art: ModelArtefact, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(art, path)
    return path


def load(path: Path) -> ModelArtefact:
    art = joblib.load(path)
    if list(art.features) != FEATURES:
        raise ValueError(f"artefact feature list {art.features} does not match FEATURES {FEATURES}")
    saved = art.lib_versions.get("sklearn", sklearn.__version__).split(".")[0]
    if saved != sklearn.__version__.split(".")[0]:
        raise ValueError(f"artefact trained with sklearn {saved}.x, runtime has {sklearn.__version__}")
    return art


# --- baseline (D12) --------------------------------------------------------------

def baseline_table(hourly: pd.DataFrame) -> dict[tuple[str, int], float]:
    """Mean near-accident rate per (condition, speed_limit) cell."""
    g = hourly.groupby(["condition", hourly["speed_limit"].astype(int)])["near_accidents"].mean()
    table = {(c, int(l)): float(v) for (c, l), v in g.items()}
    for c, v in hourly.groupby("condition")["near_accidents"].mean().items():
        table[(c, "*")] = float(v)
    table[("*", "*")] = float(hourly["near_accidents"].mean())
    return table


def baseline_predict(table, conditions, limits) -> np.ndarray:
    out = []
    for c, l in zip(conditions, limits):
        out.append(table.get((c, int(l)), table.get((c, "*"), table[("*", "*")])))
    return np.asarray(out, dtype=float)


# --- evaluation (architecture §5.3) ------------------------------------------------

def evaluate(pred: np.ndarray, y: np.ndarray, base: np.ndarray) -> dict[str, Any]:
    pred, y, base = (np.asarray(a, dtype=float) for a in (pred, y, base))
    dev = mean_poisson_deviance(y, np.maximum(pred, 1e-6))
    dev_b = mean_poisson_deviance(y, np.maximum(base, 1e-6))
    bins = pd.qcut(pd.Series(pred).rank(method="first"), 5, labels=False)
    calib = [{"bin": int(b), "mean_pred": float(pred[bins == b].mean()), "mean_obs": float(y[bins == b].mean()),
              "n": int((bins == b).sum())} for b in range(5)]
    return {
        "n": int(len(y)),
        "mae": float(mean_absolute_error(y, pred)),
        "rmse": float(np.sqrt(mean_squared_error(y, pred))),
        "poisson_dev": float(dev),
        "mae_baseline": float(mean_absolute_error(y, base)),
        "poisson_dev_baseline": float(dev_b),
        "skill": float(1 - dev / dev_b) if dev_b > 0 else 0.0,
        "sum_ratio": float(pred.sum() / y.sum()) if y.sum() else float("nan"),
        "calibration": calib,
    }


# --- monotone guard (D9) ------------------------------------------------------------

def monotone_guard(rates: Mapping[int, float]) -> dict[int, float]:
    """Make predicted rates non-increasing as the limit goes down.

    Walks the limits from highest to lowest keeping the running minimum, so a
    lower limit is never rated riskier than a higher one (blocks the confounded
    "faster is safer" curve, F04).
    """
    out: dict[int, float] = {}
    running = float("inf")
    for lim in sorted(rates, reverse=True):
        running = min(running, float(rates[lim]))
        out[lim] = running
    return dict(sorted(out.items()))
