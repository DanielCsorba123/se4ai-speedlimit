from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from speedlimit.cleaning import clean_readings, join_accidents, to_hourly
from speedlimit.config import load_config
from speedlimit.domain import Situation
from speedlimit.features import FEATURES, build_features, situation_to_frame
from speedlimit.io_load import load_accidents, load_readings, load_sensors
from speedlimit.rules import label_conditions

ROOT = Path(__file__).resolve().parents[2]
CFG = load_config(ROOT / "config.yaml")


@pytest.fixture
def hourly(tiny_readings, raw_dir):
    sensors = load_sensors(raw_dir / "sensors.csv", raw_dir / "sensor_types.csv")
    df, _ = clean_readings(load_readings(tiny_readings), sensors, CFG.cleaning)
    return to_hourly(df)


def test_feature_columns(hourly):
    X = build_features(hourly, CFG.features)
    assert list(X.columns) == FEATURES
    assert len(X) == 48 and not X.isna().any().any()


def test_log_lux_finite_for_zero(hourly):
    h = hourly.copy()
    h.iloc[0, h.columns.get_loc("lux")] = 0.0
    X = build_features(h, CFG.features)
    assert X.log_lux.iloc[0] == pytest.approx(np.log10(0.001))


def test_wind_dir_0_equals_360(hourly):
    h = hourly.iloc[:2].copy()
    h["wind_dir"] = [0.0, 360.0]
    h["wind_strength"] = [5.0, 5.0]
    X = build_features(h, CFG.features)
    assert X.wind_dir_sin.iloc[0] == pytest.approx(X.wind_dir_sin.iloc[1], abs=1e-9)
    assert X.wind_dir_cos.iloc[0] == pytest.approx(X.wind_dir_cos.iloc[1])


def test_calm_wind_zeroes_direction(hourly):
    h = hourly.iloc[:1].copy()
    h["wind_strength"], h["wind_dir"] = 0.0, 123.0
    X = build_features(h, CFG.features)
    assert X.wind_dir_sin.iloc[0] == 0 and X.wind_dir_cos.iloc[0] == 0   # D28


def test_situation_frame_rows():
    s = Situation(timestamp=datetime(2026, 1, 6, 20), lux=0.08, water_um=0.0, temp_c=-4.8, humidity=85.0,
                  noise_db=90.0, wind_strength=10.0, wind_dir_deg=180.0, traffic_cps=12.0, current_limit=60)
    X = situation_to_frame(s, [40, 50, 60, 70, 80], CFG.features)
    assert list(X.columns) == FEATURES and len(X) == 5
    assert X.speed_limit.tolist() == [40, 50, 60, 70, 80]
    assert (X.drop(columns="speed_limit").nunique() == 1).all()


def test_situation_matches_hourly_features(hourly):
    """Training and runtime must build identical features for the same hour."""
    (day, hour), row = next(iter(hourly.iterrows()))
    s = Situation(timestamp=datetime(2026, 1, day, hour), lux=row.lux, water_um=row.water, temp_c=row.temp,
                  humidity=row.humidity, noise_db=row.noise, wind_strength=row.wind_strength,
                  wind_dir_deg=row.wind_dir, traffic_cps=row.traffic, current_limit=int(row.speed_limit))
    a = build_features(hourly.iloc[:1], CFG.features).iloc[0]
    b = situation_to_frame(s, [int(row.speed_limit)], CFG.features).iloc[0]
    pd.testing.assert_series_equal(a, b, check_names=False)


@pytest.mark.realdata
def test_counts_match_facts():
    sensors = load_sensors(ROOT / "Case_Study_Speed_Limit_Sensors_V100.csv",
                           ROOT / "Case_Study_Speed_Limit_SensorTypes_V100.csv")
    df, _ = clean_readings(load_readings(ROOT / "Case_Study_Speed_Limit_SensorReadingsYearN_V100.csv"),
                           sensors, CFG.cleaning)
    h = label_conditions(join_accidents(to_hourly(df),
                                        load_accidents(ROOT / "Case_Study_Speed_Limit_AccidentsYearN_V100.csv")),
                         CFG.rules)
    assert h.dark.sum() == 354
    assert h.black_ice.sum() == 62
    assert (h.condition == "black_ice").sum() == 35
    assert h.unexplained_reduction.sum() == 28
