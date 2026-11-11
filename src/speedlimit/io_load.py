"""Robust CSV loaders for the course files (backlog Task 1).

Format quirks handled: UTF-8 BOM, ';' separator, decimal comma, CRLF, a
readings file without header (year N+1), whitespace in codes/units.

Loaders only *parse*; they never repair. Cells that don't parse become <NA>
and the original text is kept in ``<col>_raw`` so cleaning (Task 2) can repair
and count them (D19). ``LicencePlate`` is never read into memory (D20).
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

READING_COLS = ["month", "day", "hour", "minute", "second", "sensor", "value"]
ACCIDENT_COLS = {
    "Month": "month", "Day": "day", "Hour": "hour", "Second": "second",
    "Damage": "damage", "Injured": "injured", "CloseCarCm": "close_car_cm",
    "CloseGuardrailCm": "close_guardrail_cm", "SkidAngle": "skid_angle",
}
_READ = dict(sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)


def _to_float(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.str.strip().str.replace(",", ".", regex=False), errors="coerce").astype("Float64")


def _to_int(s: pd.Series) -> pd.Series:
    f = _to_float(s)
    whole = f.notna() & (f == f.round())
    return f.where(whole).astype("Int64")


def _first_cell(path: Path) -> str:
    with open(path, encoding="utf-8-sig") as fh:
        return fh.readline().split(";")[0].strip()


def load_readings(path: Path) -> pd.DataFrame:
    """Readings as nullable ints/floats plus the original text in ``<col>_raw``."""
    has_header = not re.fullmatch(r"-?\d+", _first_cell(path))
    raw = pd.read_csv(path, header=0 if has_header else None, **_READ)
    if raw.shape[1] != len(READING_COLS):
        raise ValueError(f"{path.name}: expected {len(READING_COLS)} columns, got {raw.shape[1]}")
    raw.columns = READING_COLS
    out = pd.DataFrame({c: _to_int(raw[c]) for c in READING_COLS[:-1]})
    out["value"] = _to_float(raw["value"])
    for c in READING_COLS:
        out[f"{c}_raw"] = raw[c]
    return out


def load_accidents(path: Path) -> pd.DataFrame:
    """Accident/near-accident events; LicencePlate is excluded at read time (D20)."""
    raw = pd.read_csv(path, usecols=lambda c: c in ACCIDENT_COLS, **_READ)
    raw = raw[list(ACCIDENT_COLS)].rename(columns=ACCIDENT_COLS)
    out = pd.DataFrame({c: _to_int(raw[c]) for c in ["month", "day", "hour", "second"]})
    for c in ["damage", "injured", "close_car_cm", "close_guardrail_cm", "skid_angle"]:
        out[c] = _to_float(raw[c])
    return out


def load_sensors(path: Path, types_path: Path) -> pd.DataFrame:
    """Sensors joined with their type metadata.

    Code ``T`` maps to two types (temperature, traffic); both rows are kept and
    flagged ``ambiguous`` - resolving them is cleaning's job (D2).
    """
    sensors = pd.read_csv(path, **_READ).rename(columns={"SensorID": "sensor_id", "SensorTypeCode": "code"})
    sensors["sensor_id"] = _to_int(sensors["sensor_id"])
    sensors["code"] = sensors["code"].str.strip()

    types = pd.read_csv(types_path, **_READ).rename(columns={
        "SensorTypeCode": "code", "Type": "type", "Unit": "unit", "Min": "min", "Max": "max"})
    for c in ["code", "type", "unit"]:
        types[c] = types[c].str.strip()
    types["min"], types["max"] = _to_float(types["min"]), _to_float(types["max"])
    types = types.drop_duplicates()
    types["ambiguous"] = types.duplicated("code", keep=False)

    return sensors.merge(types, on="code", how="left")[
        ["sensor_id", "code", "type", "unit", "min", "max", "ambiguous"]]
