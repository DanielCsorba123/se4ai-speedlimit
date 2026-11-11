"""Model features (D11). One code path for training and runtime."""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from speedlimit.config import FeaturesConfig
from speedlimit.domain import Situation

FEATURES: list[str] = [
    "log_lux", "water", "temp", "humidity", "noise", "wind_strength",
    "wind_dir_sin", "wind_dir_cos", "traffic", "hour_sin", "hour_cos", "speed_limit",
]


def _encode(lux, water, temp, humidity, noise, wind_strength, wind_dir, traffic, hour, speed_limit,
            cfg: FeaturesConfig) -> pd.DataFrame:
    wd = np.deg2rad(np.asarray(wind_dir, dtype=float))
    calm = np.asarray(wind_strength, dtype=float) == 0          # D28
    hr = 2 * np.pi * np.asarray(hour, dtype=float) / 24
    data = {
        "log_lux": np.log10(np.asarray(lux, dtype=float) + cfg.lux_epsilon),
        "water": np.asarray(water, dtype=float),
        "temp": np.asarray(temp, dtype=float),
        "humidity": np.asarray(humidity, dtype=float),
        "noise": np.asarray(noise, dtype=float),
        "wind_strength": np.asarray(wind_strength, dtype=float),
        "wind_dir_sin": np.where(calm, 0.0, np.sin(wd)),
        "wind_dir_cos": np.where(calm, 0.0, np.cos(wd)),
        "traffic": np.asarray(traffic, dtype=float),
        "hour_sin": np.sin(hr),
        "hour_cos": np.cos(hr),
        "speed_limit": np.asarray(speed_limit, dtype=float),
    }
    return pd.DataFrame(data)[FEATURES]


def build_features(hourly: pd.DataFrame, cfg: FeaturesConfig) -> pd.DataFrame:
    """Feature matrix for an hourly table indexed by (day, hour)."""
    X = _encode(hourly["lux"], hourly["water"], hourly["temp"], hourly["humidity"], hourly["noise"],
                hourly["wind_strength"], hourly["wind_dir"], hourly["traffic"],
                hourly.index.get_level_values("hour"), hourly["speed_limit"], cfg)
    X.index = hourly.index
    return X


def situation_to_frame(s: Situation, limits: Sequence[int], cfg: FeaturesConfig) -> pd.DataFrame:
    """One feature row per candidate speed limit for a single situation."""
    n = len(limits)
    return _encode([s.lux] * n, [s.water_um] * n, [s.temp_c] * n, [s.humidity] * n, [s.noise_db] * n,
                   [s.wind_strength] * n, [s.wind_dir_deg] * n, [s.traffic_cps] * n,
                   [s.timestamp.hour] * n, list(limits), cfg)
