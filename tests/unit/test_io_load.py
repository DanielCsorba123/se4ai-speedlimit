from pathlib import Path

import pandas as pd
import pytest

from speedlimit.io_load import load_accidents, load_readings, load_sensors

ROOT = Path(__file__).resolve().parents[2]
REAL_N = ROOT / "Case_Study_Speed_Limit_SensorReadingsYearN_V100.csv"
REAL_N1 = ROOT / "Case_Study_Speed_Limit_SensorReadingsYearNPlus1_V100.csv"
COLS = ["month", "day", "hour", "minute", "second", "sensor", "value"]


# --- readings -------------------------------------------------------------

def test_bom_stripped(tiny_readings):
    df = load_readings(tiny_readings)
    assert list(df.columns[:7]) == COLS


def test_numeric_dtypes(tiny_readings):
    df = load_readings(tiny_readings)
    assert str(df["sensor"].dtype) == "Int64"
    assert str(df["value"].dtype) == "Float64"


@pytest.mark.realdata
def test_decimal_comma():
    df = load_readings(REAL_N)
    row = df[(df.day == 1) & (df.hour == 0) & (df.minute == 22) & (df.sensor == -1)]
    assert row.value.tolist() == [70.0]


@pytest.mark.realdata
def test_n1_without_header():
    df = load_readings(REAL_N1)
    assert len(df) == 12648
    assert df.sensor.iloc[0] == 6


def test_header_detection_on_fixture(tiny_readings, tiny_readings_n1):
    a, b = load_readings(tiny_readings), load_readings(tiny_readings_n1)
    pd.testing.assert_frame_equal(a[COLS], b[COLS])


def test_dirty_cells_become_na_and_raw_text_is_kept(faulty_readings):
    df = load_readings(faulty_readings)
    null_rows = df[df.month_raw == "NULL"]
    assert len(null_rows) > 0 and null_rows.month.isna().all()
    assert (df.month_raw == "January").any()
    assert df.sensor.isna().any()          # empty sensor id
    assert df.value.isna().any()           # empty readings
    assert len(df) == 816                  # no row silently dropped


def test_clean_file_has_no_na(tiny_readings):
    assert not load_readings(tiny_readings)[COLS].isna().any().any()


# --- accidents --------------------------------------------------------------

def test_licence_plate_dropped(tiny_accidents):
    df = load_accidents(tiny_accidents)
    assert not any("plate" in c.lower() for c in df.columns)


def test_accident_columns_and_types(tiny_accidents):
    df = load_accidents(tiny_accidents)
    assert list(df.columns) == ["month", "day", "hour", "second", "damage", "injured",
                                "close_car_cm", "close_guardrail_cm", "skid_angle"]
    assert len(df) == 20
    assert str(df.hour.dtype) == "Int64"
    assert df.close_car_cm.notna().any()


# --- sensors ----------------------------------------------------------------

def test_type_codes_stripped(raw_dir):
    df = load_sensors(raw_dir / "sensors.csv", raw_dir / "sensor_types.csv")
    assert "W" in set(df.code)
    assert "W " not in set(df.code)
    assert (df.unit == df.unit.str.strip()).all()


def test_ambiguous_code_t_flagged(raw_dir):
    df = load_sensors(raw_dir / "sensors.csv", raw_dir / "sensor_types.csv")
    s16 = df[df.sensor_id == 16]
    assert set(s16.type) == {"temperature", "traffic"}
    assert s16.ambiguous.all()
    assert not df[df.sensor_id == 1].ambiguous.any()


def test_sensor_ranges_numeric(raw_dir):
    df = load_sensors(raw_dir / "sensors.csv", raw_dir / "sensor_types.csv")
    wd = df[df.code == "WD"].iloc[0]
    assert (wd["min"], wd["max"]) == (0, 360)


def test_duplicate_type_rows_collapsed(raw_dir, tmp_path):
    """A types file listing WD twice must still give one row per WD sensor (robustness, D19)."""
    types = (raw_dir / "sensor_types.csv").read_text(encoding="utf-8-sig")
    wd = next(line for line in types.splitlines() if line.startswith("WD"))
    dup = tmp_path / "types_dup.csv"
    dup.write_text(types + "\n" + wd, encoding="utf-8")
    df = load_sensors(raw_dir / "sensors.csv", dup)
    assert (df[df.code == "WD"].sensor_id.value_counts() == 1).all()
    assert not df[df.code == "WD"].ambiguous.any()
