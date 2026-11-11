from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from speedlimit.cleaning import (SENSOR_GROUPS, CleaningReport, clean_readings, join_accidents,
                                 resolve_sensor_types, to_hourly)
from speedlimit.config import load_config
from speedlimit.io_load import load_accidents, load_readings, load_sensors

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def cfg():
    return load_config(ROOT / "config.yaml").cleaning


@pytest.fixture
def sensors(raw_dir):
    return load_sensors(raw_dir / "sensors.csv", raw_dir / "sensor_types.csv")


@pytest.fixture
def faulty(faulty_readings, sensors, cfg):
    return clean_readings(load_readings(faulty_readings), sensors, cfg)


@pytest.fixture
def clean_tiny(tiny_readings, sensors, cfg):
    return clean_readings(load_readings(tiny_readings), sensors, cfg)


# --- sensor registry (D2, D3) ---------------------------------------------------

def test_sensor_type_resolution(sensors):
    m = resolve_sensor_types(sensors)
    assert m[16] == "traffic"
    assert m[19] == "temperature"
    assert m[15] == m[18] == "temperature"
    assert m[-1] == "speed_limit"
    assert 7 not in m and 10 not in m and 17 not in m


def test_silent_sensors_reported(clean_tiny):
    _, rep = clean_tiny
    assert rep.silent_sensors == [7, 10, 17]


# --- injected slide-17 faults (D19) --------------------------------------------------

def test_text_month_repaired(faulty):
    df, rep = faulty
    assert (df.month == 1).all()
    assert rep.count("C08") >= 6 + 6       # 6 "January" + 6 "NULL" rows


def test_null_month_imputed(faulty_readings, sensors, cfg):
    raw = load_readings(faulty_readings)
    null_idx = raw.index[raw.month_raw == "NULL"]
    df, _ = clean_readings(raw, sensors, cfg)
    assert df.loc[df.index.intersection(null_idx), "month"].eq(1).all()


def test_missing_sensor_id_inferred(faulty):
    df, rep = faulty
    assert rep.count("C06") == 2
    s18 = df[(df.sensor == 18) & (df.day == 6)]
    assert len(s18) == 24                    # 22h and 23h re-attached to sensor 18
    assert df.sensor.notna().all()


def test_out_of_range_wind_direction(faulty):
    df, rep = faulty
    wd13 = df[(df.sensor == 13) & (df.day == 5) & df.hour.between(12, 14)]
    assert (wd13.value <= 360).all() and wd13.value.notna().all()
    assert wd13.imputed.all()
    assert rep.count("C09") >= 3


def test_extreme_value_removed(faulty):
    df, rep = faulty
    v = df[(df.sensor == 11) & (df.day == 6) & (df.hour == 9)].value.iloc[0]
    assert v <= 10000
    assert rep.count("C09") >= 4             # 3 x wind direction + 1 x water


def test_empty_values_filled_from_siblings(faulty):
    df, rep = faulty
    s18 = df[(df.sensor == 18) & (df.day == 5) & (df.hour <= 4)].sort_values("hour")
    siblings = df[df.sensor.isin([15, 19]) & (df.day == 5) & (df.hour <= 4)]
    expect = siblings.groupby("hour").value.mean().sort_index().to_numpy()
    np.testing.assert_allclose(s18.value.to_numpy(dtype=float), expect.astype(float))
    assert rep.count("C07") >= 5


def test_duplicate_day_removed(faulty):
    df, rep = faulty
    s4 = df[(df.sensor == 4) & (df.day == 5)]
    assert len(s4) == 24
    assert rep.count("C12") == 24


def test_raw_columns_dropped(faulty):
    df, _ = faulty
    assert not [c for c in df.columns if c.endswith("_raw")]


def test_report_is_list_of_events(faulty):
    _, rep = faulty
    assert isinstance(rep, CleaningReport)
    assert all(len(e) == 3 for e in rep.events)


# --- hourly table ------------------------------------------------------------

def test_hourly_shape_and_columns(clean_tiny):
    hourly = to_hourly(clean_tiny[0])
    assert len(hourly) == 48
    assert list(hourly.index.names) == ["day", "hour"]
    for col in list(SENSOR_GROUPS) + ["speed_limit", "complete"]:
        assert col in hourly.columns
    assert "temp_spread" in hourly.columns


def test_missing_day_covered_by_siblings(faulty):
    hourly = to_hourly(faulty[0])
    assert hourly.loc[6, "temp"].notna().all()       # sensor 15 missing on Jan 6
    assert hourly.complete.all()


def test_wind_direction_circular_mean():
    df = pd.DataFrame({"month": 1, "day": 1, "hour": 0, "sensor": [5, 13], "value": [350.0, 10.0],
                       "imputed": False})
    hourly = to_hourly(df)
    wd = hourly.loc[(1, 0), "wind_dir"]
    assert min(wd, 360 - wd) < 1e-6


# --- accidents ----------------------------------------------------------------

def test_hour_mapping(clean_tiny):
    hourly = to_hourly(clean_tiny[0])
    acc = pd.DataFrame({"month": [1, 1], "day": [5, 5], "hour": [24, 1], "second": [0, 0],
                        "damage": [np.nan, np.nan], "injured": [np.nan, np.nan],
                        "close_car_cm": [10.0, 12.0], "close_guardrail_cm": [np.nan, np.nan],
                        "skid_angle": [np.nan, np.nan]})
    out = join_accidents(hourly, acc)
    assert out.loc[(5, 23), "near_accidents"] == 1
    assert out.loc[(5, 0), "near_accidents"] == 1
    assert out.near_accidents.sum() == 2


def test_empty_accident_row_rejected(clean_tiny):
    hourly = to_hourly(clean_tiny[0])
    acc = pd.DataFrame({"month": [1], "day": [5], "hour": [3], "second": [0], "damage": [np.nan],
                        "injured": [np.nan], "close_car_cm": [np.nan], "close_guardrail_cm": [np.nan],
                        "skid_angle": [np.nan]})
    out = join_accidents(hourly, acc)
    assert out.near_accidents.sum() == 0 and out.accidents.sum() == 0


# --- real data (V100) -------------------------------------------------------------

@pytest.mark.realdata
def test_real_counts(cfg):
    sensors = load_sensors(ROOT / "Case_Study_Speed_Limit_Sensors_V100.csv",
                           ROOT / "Case_Study_Speed_Limit_SensorTypes_V100.csv")
    df, rep = clean_readings(load_readings(ROOT / "Case_Study_Speed_Limit_SensorReadingsYearN_V100.csv"),
                             sensors, cfg)
    hourly = join_accidents(to_hourly(df), load_accidents(ROOT / "Case_Study_Speed_Limit_AccidentsYearN_V100.csv"))
    assert len(hourly) == 744
    assert hourly.near_accidents.sum() == 964
    assert hourly.accidents.sum() == 32
    assert hourly.complete.all()
    # on clean V100 only the structural rules fire (data report §8)
    fired = {e[0] for e in rep.events if e[1] > 0}
    assert fired <= {"C04", "C05"}, rep.events


def test_in_range_spike_replaced_by_siblings(tiny_readings, sensors, cfg):
    """C10: water sensor 1 reads 9000 um (in range) while siblings 8 and 11 read ~0."""
    raw = load_readings(tiny_readings)
    hit = raw.index[(raw.sensor == 1) & (raw.day == 5) & (raw.hour == 12)]
    raw.loc[hit, "value"] = 9000.0
    df, rep = clean_readings(raw, sensors, cfg)
    v = df[(df.sensor == 1) & (df.day == 5) & (df.hour == 12)].value.iloc[0]
    sib = df[df.sensor.isin([8, 11]) & (df.day == 5) & (df.hour == 12)].value.mean()
    assert rep.count("C10") == 1
    assert v == pytest.approx(sib)


# --- review I-5 (C07 / D30) -------------------------------------------------------------

def _blank(raw, sensors_, day, hours):
    hit = raw.index[raw.sensor.isin(sensors_) & (raw.day == day) & raw.hour.isin(hours)]
    raw.loc[hit, "value"] = float("nan")
    return raw


def test_whole_type_missing_is_not_interpolated(tiny_readings, sensors, cfg):
    """All three temperature sensors empty for two hours -> hour incomplete, excluded (D30)."""
    raw = _blank(load_readings(tiny_readings), [15, 18, 19], 5, [10, 11])
    df, rep = clean_readings(raw, sensors, cfg)
    hourly = to_hourly(df)
    assert not hourly.loc[(5, 10), "complete"] and not hourly.loc[(5, 11), "complete"]
    assert hourly.loc[(5, 9), "complete"]


def test_single_sensor_short_gap_interpolated_long_gap_not(tiny_readings, sensors, cfg):
    raw = _blank(load_readings(tiny_readings), [4], 5, [8, 9])                       # 2 h humidity gap
    raw = _blank(raw, [4], 6, list(range(5, 11)))                                     # 6 h humidity gap
    df, _ = clean_readings(raw, sensors, cfg)
    hourly = to_hourly(df)
    assert hourly.loc[(5, 8), "complete"] and hourly.loc[(5, 9), "complete"]
    assert not hourly.loc[(6, 7), "complete"]
