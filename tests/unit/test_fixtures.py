"""Contract for the small CSV fixtures that Tasks 1–3 build on."""
import pandas as pd

READ_COLS = ["Month", "Day", "Hour", "Minute", "Second", "Sensor", "Value"]


def _read(p, **kw):
    # keep_default_na=False: pandas would otherwise turn the literal "NULL" into NaN
    return pd.read_csv(p, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False, **kw)


def test_tiny_readings_is_two_full_days(tiny_readings):
    df = _read(tiny_readings)
    assert list(df.columns) == READ_COLS
    assert sorted(df.Day.astype(int).unique()) == [5, 6]
    assert len(df) == 2 * 24 * 17  # 17 reporting series incl. speed limit -1
    assert "," in df.Value.iloc[0] or df.Value.str.contains(",").any()  # decimal comma kept


def test_tiny_n1_has_no_header(tiny_readings_n1):
    first = tiny_readings_n1.read_text(encoding="utf-8-sig").splitlines()[0]
    assert first.split(";")[0].isdigit()


def test_tiny_accidents_has_20_rows_with_plates(tiny_accidents):
    df = _read(tiny_accidents)
    assert len(df) == 20
    assert "LicencePlate" in df.columns  # loader must drop it (D20), so the fixture keeps it


def test_metadata_fixtures_copied(raw_dir):
    assert (raw_dir / "sensors.csv").is_file()
    assert (raw_dir / "sensor_types.csv").is_file()


def test_fault_fixture_contains_each_slide17_class(faulty_readings):
    df = _read(faulty_readings)
    assert (df.Month == "January").any()
    assert (df.Month == "NULL").any()
    assert df.Sensor.isna().any() or (df.Sensor == "").any()
    wd = pd.to_numeric(df[df.Sensor == "13"].Value.str.replace(",", "."), errors="coerce")
    assert (wd > 360).any()
    sensor4 = df[df.Sensor == "4"]
    assert sensor4.duplicated(["Day", "Hour"]).sum() == 24       # one duplicated day
    sensor15 = df[df.Sensor == "15"]
    assert len(sensor15) == 24                                   # one of two days missing
    assert (df.Value == "").any() or df.Value.isna().any()       # empty readings
